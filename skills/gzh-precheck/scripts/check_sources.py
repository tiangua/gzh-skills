#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""公众号文章发布前的确定性检查，通过后打出手动发布包。

只做能用规则判断的部分；事实是否被来源支持、语气是否得体，仍需执行者逐条打开来源人工核对。

检查项（错误 = 阻断发布；警告 = 需要人看一眼）：
  元数据   标题 ≤32 字、摘要 ≤120 字、作者 ≤16 字（公众号官方草稿接口文档）
  出处     含数字、日期、引语或“发布/宣布/表示/据”等归因词的句子，所在段落必须有链接或脚注
  脚注     引用与定义一一对应；出处必须是 http(s) 链接，不能是搜索结果页或占位链接
  限定词   与初稿相比，“可能/据称/计划/预计/尚未/约/超过……”不能变少（防止把含糊说法改成确定）
  数字     终稿不能出现初稿没有的数字；标题里的数字必须在正文出现
  绝对化   “最/第一/唯一/100%/绝对/保证……”给出警告；出现在标题里视为错误
  对照表   已核实的“事实”行必须有出处；列出“待核实/不支持”的行供人工确认未进入正文
  HTML     调用 gzh-format 的合规检查
  封面     读取 gzh-cover 的自检结果
  链接     --online 时逐个请求出处链接，打不开的给出警告

用法：
  check_sources.py --final 03-final.md [--draft 02-draft.md] [--claims 02-claims.md] \
      [--html 04-article.html] [--cover-audit 05-cover-audit.json] [--online] \
      [--json-out 06-precheck.json] [--report 06-precheck.md] [--package package/]
退出码：0 = 通过；1 = 不通过。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORMAT_SCRIPTS = HERE.parent.parent / "gzh-format" / "scripts"

LIMITS = {"title": 32, "author": 16, "digest": 120}
HEDGES = ["可能", "或许", "也许", "据称", "据报道", "据悉", "传闻", "疑似", "计划", "预计", "拟", "有望",
          "尚未", "未经证实", "仅", "约", "大约", "左右", "超过", "至少", "不到", "接近", "部分", "初步", "暂",
          "目前", "截至", "声称", "认为", "如果", "或"]
CERTAINTY = ["必然", "必将", "将会", "一定", "肯定", "确定", "证实", "已经", "彻底", "完全"]
ABSOLUTE = ["最", "第一", "唯一", "首个", "100%", "百分之百", "绝对", "永远", "保证", "没有之一",
            "史上", "全网", "顶级", "无敌", "颠覆", "革命性"]
ABS_OK = ["最近", "最新", "最后", "最初", "最早", "最多", "最少", "最好", "第一次", "第一步", "第一个问题", "第一节", "第一批", "第一条", "第一项", "第一种", "第一部分", "第一天", "第一周", "第一版", "第一稿", "第一阶段"]
ATTRIB = ["发布", "宣布", "表示", "称", "显示", "报告", "据", "披露", "公布", "推出", "开源", "上线", "写道", "指出", "提到", "更新", "调整", "改为"]
OPINION = ["我认为", "我的判断", "我觉得", "我们认为", "在我看来", "我猜", "建议"]
BAD_SOURCE = [r"google\.[a-z.]+/search", r"bing\.com/search", r"baidu\.com/s\?", r"sogou\.com/web",
              r"example\.(com|org|net)", r"\.invalid\b", r"localhost", r"replace-me"]
NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?")


# ----------------------------------------------------------------------------- parsing
def read(p):
    return Path(p).read_text(encoding="utf-8") if p else ""


def split_front_matter(text: str):
    sys.path.insert(0, str(FORMAT_SCRIPTS))
    from wechat_html import split_front_matter as sfm  # 复用 gzh-format 的解析
    return sfm(text)


def body_blocks(body: str):
    """返回 (正文块列表, 脚注定义 dict)。块 = 段落 / 列表项 / 引用；跳过代码、注释、标题。"""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"^(```|~~~).*?^\1\s*$", "", body, flags=re.S | re.M)
    footdefs = {}
    for m in re.finditer(r"^\[\^([^\]]+)\]:\s*(.+)$", body, flags=re.M):
        footdefs[m.group(1)] = m.group(2).strip()
    body = re.sub(r"^\[\^([^\]]+)\]:\s*(.+)$", "", body, flags=re.M)
    blocks, cur = [], []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|"):
            if cur and not cur[0].startswith("TABLE\u241f"):
                blocks.append(" ".join(cur)); cur = []
            if not re.match(r"^\|?\s*:?-{3,}", s):
                cur = cur or ["TABLE\u241f"]
                cur.append(s)
            continue
        if cur and cur[0].startswith("TABLE\u241f"):
            blocks.append(" ".join(cur)); cur = []
        if not s or re.match(r"^#{1,6}\s", s) or re.match(r"^[-*_]{3,}$", s) or re.match(r"^\|?\s*:?-{3,}", s):
            if cur:
                blocks.append(" ".join(cur)); cur = []
            continue
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            if cur:
                blocks.append(" ".join(cur)); cur = []
            s = re.sub(r"^([-*+]|\d+[.)])\s+", "", s)
        s = re.sub(r"^>\s?", "", s)
        cur.append(s)
    if cur:
        blocks.append(" ".join(cur))
    return blocks, footdefs


def headings(body: str):
    body = re.sub(r"^(```|~~~).*?^\1\s*$", "", body, flags=re.S | re.M)
    return [re.sub(r"^#{1,6}\s+", "", l.strip()) for l in body.splitlines() if re.match(r"^\s*#{1,6}\s", l)]


def strip_links(text: str) -> str:
    """去掉链接目标和脚注编号，只留可见文字（用于数数字、找限定词）。"""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\^[^\]]+\]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    return text


def has_source(block: str) -> bool:
    return bool(re.search(r"\]\(https?://", block) or re.search(r"\[\^[^\]]+\]", block) or re.search(r"https?://", block))


def sentences(block: str):
    parts = re.split(r"(?<=[。！？!?；])", block)
    return [p.strip() for p in parts if p.strip()]


def is_factual(sentence: str) -> bool:
    vis = strip_links(sentence)
    if NUM_RE.search(vis):
        return True
    if re.search(r"[“\"「].{4,}?[”\"」]", vis):
        return True
    if any(w in vis for w in ATTRIB) and not any(o in vis for o in OPINION):
        return True
    return False


def count_terms(text: str, terms):
    vis = strip_links(text)
    out = {}
    for t in terms:
        if t == "约":
            n = len(re.findall(r"约(?=\s*\d|\s*[一二三四五六七八九十百千万])", vis))
        elif t == "仅":
            n = len(re.findall(r"(?<!不)仅", vis))
        elif t == "或":
            n = len(re.findall(r"或(?!许|者)", vis))
        else:
            n = vis.count(t)
        if n:
            out[t] = n
    return out


def contexts(text: str, term: str, width: int = 18, limit: int = 3):
    vis = strip_links(text)
    res = []
    for m in re.finditer(re.escape(term), vis):
        res.append("…" + vis[max(0, m.start() - width): m.end() + width].replace("\n", " ") + "…")
        if len(res) >= limit:
            break
    return res


def urls_in(text: str):
    return set(u.rstrip(").,，。") for u in re.findall(r"https?://[^\s)\]>\"']+", text))


# ----------------------------------------------------------------------------- checks
def run(args) -> dict:
    errors, warnings, info = [], [], {}
    final_raw = read(args.final)
    meta, final_body = split_front_matter(final_raw)
    blocks, footdefs = body_blocks(final_body)
    full_text = "\n".join(b.replace("TABLE\u241f", "") for b in blocks)

    # 元数据
    title = str(meta.get("title") or "")
    if not title:
        errors.append("缺少标题（front matter 的 title）")
    for k, lim in LIMITS.items():
        v = str(meta.get(k) or "")
        if len(v) > lim:
            errors.append(f"{k} 共 {len(v)} 字，超过公众号上限 {lim} 字")
    if not meta.get("digest"):
        warnings.append("没有摘要：公众号会默认抓取正文前 54 个字")

    # 出处覆盖
    unsourced, factual_n = [], 0
    for i, b in enumerate(blocks):
        if b.startswith("TABLE\u241f"):
            ok = has_source(b) or any(has_source(blocks[j]) for j in (i - 1, i + 1) if 0 <= j < len(blocks))
            if is_factual(b):
                factual_n += 1
                if not ok:
                    unsourced.append("（表格）" + b.replace("TABLE\u241f", "")[:60])
            continue
        for s in sentences(b):
            if is_factual(s):
                factual_n += 1
                if not has_source(b):
                    unsourced.append(s)
    info["factual_sentences"] = factual_n
    info["unsourced_sentences"] = len(unsourced)
    for s in unsourced:
        errors.append(f"疑似事实句没有出处：{strip_links(s)[:80]}")

    # 脚注与链接
    refs = set(re.findall(r"\[\^([^\]]+)\](?!:)", final_body))
    for r in sorted(refs - set(footdefs)):
        errors.append(f"脚注 [^{r}] 没有定义")
    for r in sorted(set(footdefs) - refs):
        warnings.append(f"脚注 [^{r}] 定义了但正文没有引用")
    for fid, d in footdefs.items():
        if not re.search(r"https?://", d):
            errors.append(f"脚注 [^{fid}] 没有链接：{d[:60]}")
    all_urls = urls_in(final_body)
    info["source_urls"] = sorted(all_urls)
    for u in sorted(all_urls):
        for pat in BAD_SOURCE:
            if re.search(pat, u):
                (warnings if args.allow_placeholders else errors).append(f"出处不合格（搜索结果页或占位链接）：{u}")
                break

    # 绝对化用语
    vis_full = strip_links(full_text)
    for w in ABSOLUTE:
        for m in re.finditer(re.escape(w), vis_full):
            tail = vis_full[m.start(): m.start() + 6]
            if any(tail.startswith(ok) for ok in ABS_OK):
                continue
            ctx = vis_full[max(0, m.start() - 18): m.end() + 18].replace("\n", " ")
            warnings.append(f"绝对化用语“{w}”：…{ctx}…（有出处的客观排名可保留）")
            break
        if w in title and not any(ok in title for ok in ABS_OK):
            errors.append(f"标题含绝对化用语“{w}”")

    # 标题里的数字必须在正文出现
    for n in NUM_RE.findall(title):
        if n not in strip_links(full_text):
            errors.append(f"标题里的数字 {n} 没有出现在正文中")

    # 与初稿对比
    if args.draft:
        d_meta, d_body = split_front_matter(read(args.draft))
        d_blocks, _ = body_blocks(d_body)
        d_text = "\n".join(b.replace("TABLE\u241f", "") for b in d_blocks)
        dh, fh = count_terms(d_text, HEDGES), count_terms(full_text, HEDGES)
        for t, n in dh.items():
            if fh.get(t, 0) < n:
                errors.append(f"限定词“{t}”从初稿的 {n} 处减少到 {fh.get(t, 0)} 处，确认没有把含糊说法改成确定说法："
                              + " / ".join(contexts(d_text, t)))
        dc, fc = count_terms(d_text, CERTAINTY), count_terms(full_text, CERTAINTY)
        for t, n in fc.items():
            if n > dc.get(t, 0):
                warnings.append(f"确定性词“{t}”比初稿多 {n - dc.get(t, 0)} 处：" + " / ".join(contexts(full_text, t)))
        dn = set(NUM_RE.findall(strip_links(d_text)))
        fn = set(NUM_RE.findall(strip_links(full_text)))
        for n in sorted(fn - dn):
            errors.append(f"终稿出现了初稿没有的数字 {n}：" + " / ".join(contexts(full_text, n, limit=1)))
        for n in sorted(dn - fn):
            warnings.append(f"初稿里的数字 {n} 在终稿中消失了，确认是有意删除")
        du, fu = urls_in(d_body), all_urls
        for u in sorted(du - fu):
            warnings.append(f"初稿里的出处在终稿中消失：{u}")
        for u in sorted(fu - du):
            warnings.append(f"终稿新增了初稿没有的出处，确认已经核对：{u}")
        info["hedges_draft"], info["hedges_final"] = dh, fh

    # 对照表
    if args.claims:
        rows = [l for l in read(args.claims).splitlines() if re.match(r"^\|\s*C\d+", l)]
        pending = []
        for l in rows:
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if len(cells) < 6:
                continue
            cid, claim, typ, _ev, src, status = cells[:6]
            if typ == "事实" and status == "已核实" and not re.search(r"https?://", src):
                errors.append(f"对照表 {cid} 标为已核实的事实却没有出处链接")
            if status in ("待核实", "不支持"):
                pending.append(f"{cid}（{status}）：{claim}")
        info["claims_rows"] = len(rows)
        for p in pending:
            warnings.append(f"对照表 {p} —— 人工确认它没有进入正文")

    # HTML
    if args.html:
        sys.path.insert(0, str(FORMAT_SCRIPTS))
        from wechat_html import check_html
        rep = check_html(read(args.html), meta)
        info["html"] = rep["stats"]
        errors += [f"HTML：{e}" for e in rep["errors"]]
        warnings += [f"HTML：{w}" for w in rep["warnings"]]
    else:
        warnings.append("没有提供 HTML，跳过排版合规检查")

    # 封面
    if args.cover_audit:
        ca = json.loads(read(args.cover_audit))
        info["cover_pass"] = ca.get("pass")
        if not ca.get("pass"):
            errors += [f"封面：{p}" for p in ca.get("problems", [])] or ["封面自检未通过"]
        for k in ("cover_235",):
            f = ca.get("files", {}).get(k)
            if f and not Path(f).exists() and not (Path(args.cover_audit).parent / Path(f).name).exists():
                errors.append(f"封面文件不存在：{f}")
    else:
        warnings.append("没有提供封面自检结果，跳过封面检查")

    # 在线检查链接
    if args.online:
        import urllib.request
        for u in sorted(all_urls):
            try:
                req = urllib.request.Request(u, method="GET", headers={"User-Agent": "Mozilla/5.0 gzh-precheck"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    code = r.status
            except Exception as e:  # noqa: BLE001
                code = getattr(e, "code", None) or str(e)[:60]
            if not (isinstance(code, int) and code < 400):
                warnings.append(f"出处链接打不开（{code}）：{u}（有些网站拒绝脚本访问，请人工打开确认）")

    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    return {"pass": not errors, "publish_mode": "manual", "title": title, "digest": meta.get("digest", ""),
            "author": meta.get("author", ""), "source_url": meta.get("source_url", ""),
            "errors": errors, "warnings": warnings, "info": info}


def write_report(res: dict, path: str) -> None:
    lines = [f"# 发布前检查：{'通过' if res['pass'] else '不通过'}", "",
             f"- 标题：{res['title']}", f"- 摘要：{res['digest']}", "- 发布方式：手动（固定）",
             f"- 疑似事实句：{res['info'].get('factual_sentences', 0)}，其中无出处：{res['info'].get('unsourced_sentences', 0)}",
             f"- 出处链接：{len(res['info'].get('source_urls', []))} 个", ""]
    lines.append("## 错误（必须修复）")
    lines += [f"- {e}" for e in res["errors"]] or ["- 无"]
    lines += ["", "## 警告（逐条人工确认）"]
    lines += [f"- {w}" for w in res["warnings"]] or ["- 无"]
    lines += ["", "## 人工核对（脚本做不到，必须由审稿人完成）",
              "- [ ] 逐条打开出处，确认来源确实支持正文的说法，且没有夸大",
              "- [ ] 引语与原文一字不差，译文已注明",
              "- [ ] 没有编造的个人经历、对话、采访",
              "- [ ] 图片均有授权或为自制",
              "- [ ] 标题与正文一致，没有标题党"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_package(res: dict, args) -> list[str]:
    pkg = Path(args.package)
    pkg.mkdir(parents=True, exist_ok=True)
    made = []
    if args.html:
        shutil.copy(args.html, pkg / "article.html"); made.append("article.html")
    if args.cover_audit:
        ca = json.loads(read(args.cover_audit))
        for key, name in (("cover_235", "cover-235.png"), ("cover_1x1_preview", "cover-1x1-preview.png")):
            f = ca.get("files", {}).get(key)
            cand = [Path(f)] if f else []
            if f:
                cand.append(Path(args.cover_audit).parent / Path(f).name)
            for c in cand:
                if c.exists():
                    shutil.copy(c, pkg / name); made.append(name); break
        crop = ca.get("wechat_crop_hint", {})
    else:
        crop = {}
    refs = "\n".join(f"- {u}" for u in res["info"].get("source_urls", [])) or "- 无"
    crop_note = crop.get("note", "")
    publish = f"""# 手动发布包

> 本包只供人工发布使用。不要用任何脚本或接口自动群发 / 发布。

| 字段 | 内容 |
|---|---|
| 标题 | {res['title']} |
| 摘要 | {res['digest']} |
| 作者 | {res['author'] or '（可空）'} |
| 阅读原文链接 | {res['source_url'] or '（可空）'} |

## 后台操作步骤
1. 新建图文，填写上面的标题、作者、摘要。
2. 用浏览器打开 `article.html`（或预览页），全选复制正文，粘贴进编辑器。
3. 上传 `cover-235.png` 作为封面；设置 1:1 裁剪框。{crop_note}
4. 正文里的本地图片需要在编辑器里重新上传。
5. 手机预览，确认参考资料编号、表格、代码块显示正常。
6. 人工确认无误后，由你本人点击发布。

## 出处清单
{refs}

## 检查警告（发布前请再看一眼）
""" + ("\n".join(f"- {w}" for w in res["warnings"]) or "- 无") + "\n"
    (pkg / "publish.md").write_text(publish, encoding="utf-8"); made.append("publish.md")
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="公众号发布前检查")
    ap.add_argument("--final", required=True)
    ap.add_argument("--draft")
    ap.add_argument("--claims")
    ap.add_argument("--html")
    ap.add_argument("--cover-audit")
    ap.add_argument("--online", action="store_true", help="逐个请求出处链接")
    ap.add_argument("--allow-placeholders", action="store_true", help="把占位链接降为警告（只用于样例）")
    ap.add_argument("--json-out")
    ap.add_argument("--report")
    ap.add_argument("--package", help="通过时生成手动发布包的目录")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    res = run(a)
    if a.package and res["pass"]:
        res["package"] = {"dir": a.package, "files": make_package(res, a)}
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.report:
        write_report(res, a.report)
    if not a.quiet:
        print(("✅ 通过" if res["pass"] else "❌ 不通过") + f"  错误 {len(res['errors'])}，警告 {len(res['warnings'])}")
        for e in res["errors"]:
            print(f"  错误：{e}")
        for w in res["warnings"]:
            print(f"  警告：{w}")
        if res.get("package"):
            print(f"  发布包：{a.package}（{', '.join(res['package']['files'])}）")
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
