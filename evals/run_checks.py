#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""gzh-skills 的脚本类回归检查。

子命令：
  skills    检查每个 skills/*/SKILL.md 的 frontmatter（name 与目录一致、description 单行），
            以及正文里没有写死的机器人名、账号名
  format    用 gzh-format 转换示例终稿，确认无错误、无 class/<style>、外链已转成参考资料
  cover     跑封面像素自检的 selftest；有 Playwright 时渲染示例封面并要求自检通过
  precheck  跑 evals/precheck-cases 的埋雷用例，确认该报错的都报错、干净稿通过；再检查示例终稿
  humanize  自测改写保留检查器：reference_output 必须通过、bad_output 必须失败；
            也可以检查真实改写结果：
              run_checks.py humanize --original 02-draft.md --edited 03-final.md
              run_checks.py humanize --cases outputs.json   # {"case_id": "改写结果", ...}
  skillchange  技能改动的合入前检查（evals/check_skill_change.py）：先自测规则，再全量检查所有技能，
            最后检查工作区相对 HEAD 的改动（正文过长、参考文件膨胀、混进日期或聊天记录）
  all       依次运行以上全部（默认）
退出码：0 = 全部通过。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
EXAMPLE = ROOT / "examples" / "2026-10-20-digest-limit"
sys.path.insert(0, str(ROOT / "skills" / "gzh-format" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "gzh-precheck" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "gzh-cover" / "scripts"))

BOT_SPECIFIC = ["X热点", "Lunar", "tiangua", "phantom", "Grok", "公众号主笔", "lunar.zhou"]
RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


# ----------------------------------------------------------------------------- skills
def check_skills() -> bool:
    ok = True
    dirs = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    for d in dirs:
        f = d / "SKILL.md"
        if not f.exists():
            ok &= record(f"skills/{d.name}", False, "缺少 SKILL.md"); continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            ok &= record(f"skills/{d.name}", False, "缺少 YAML frontmatter"); continue
        fm = m.group(1)
        name = re.search(r"^name:\s*(.+)$", fm, re.M)
        desc = re.search(r"^description:\s*(.+)$", fm, re.M)
        problems = []
        if not name or name.group(1).strip() != d.name:
            problems.append("name 与目录名不一致")
        if not desc or desc.group(1).strip() in ("|", ">", ">-", "|-"):
            problems.append("description 必须是单行")
        extra = [l.split(":")[0] for l in fm.splitlines() if re.match(r"^\w", l) and l.split(":")[0] not in ("name", "description")]
        if extra:
            problems.append(f"frontmatter 有多余字段 {extra}")
        hits = [w for w in BOT_SPECIFIC if w in text]
        if hits:
            problems.append(f"正文含特定机器人/账号信息 {hits}")
        ok &= record(f"skills/{d.name}", not problems, "; ".join(problems))
    ok &= record("skills 数量为 7", len(dirs) == 7, f"实际 {len(dirs)}")
    return ok


# ----------------------------------------------------------------------------- format
def check_format() -> bool:
    import wechat_html as wh
    md = (EXAMPLE / "03-final.md").read_text(encoding="utf-8")
    frag, meta, theme, warns = wh.convert(md)
    rep = wh.check_html(frag, meta)
    ok = record("format 示例终稿无错误", rep["ok"], "; ".join(rep["errors"]))
    ok &= record("format 无 class / <style> / <script>", not re.search(r'\sclass=|<style|<script', frag))
    ok &= record("format 外链已转成参考资料", "<a " not in frag and "参考资料" in frag)
    ok &= record("format 引语未被改动", "“api摘要长度限制对齐mp端120字”" in frag)
    for t in ("classic", "grace"):
        f2, m2, _, _ = wh.convert(md, t)
        ok &= record(f"format 主题 {t} 可用", wh.check_html(f2, m2)["ok"])
    bad = '<section class="x"><style>p{}</style><p style="position: fixed">x</p></section>'
    r = wh.check_html(bad)
    ok &= record("format 检查器能抓出违规 HTML", not r["ok"] and len(r["errors"]) >= 3)
    return ok


# ----------------------------------------------------------------------------- cover
def check_cover() -> bool:
    py = sys.executable
    r = subprocess.run([py, str(ROOT / "skills/gzh-cover/scripts/audit.py"), "--selftest"], capture_output=True, text=True)
    ok = record("cover 像素自检 selftest", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    try:
        import playwright  # noqa: F401
    except ImportError:
        record("cover 渲染示例（跳过：没有 Playwright）", True)
        return ok
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([py, str(ROOT / "skills/gzh-cover/scripts/render.py"), "--spec", str(EXAMPLE / "cover.json"),
                            "--out", f"{td}/c"], capture_output=True, text=True)
        ok &= record("cover 渲染示例并通过自检", r.returncode == 0, (r.stdout + r.stderr).strip()[-300:])
        long = subprocess.run([py, str(ROOT / "skills/gzh-cover/scripts/render.py"), "--out", f"{td}/long",
                               "--title", "这是一个故意写得非常长的标题，用来确认封面自检能发现标题超过三行的问题并给出提示",
                               "--mark", "TEST"], capture_output=True, text=True)
        ok &= record("cover 能发现标题溢出", long.returncode == 1 and "超过上限" in long.stdout, long.stdout.strip()[-200:])
    return ok


# ----------------------------------------------------------------------------- precheck
def check_precheck() -> bool:
    import check_sources as cs
    base = EVALS / "precheck-cases"
    cases = json.loads((base / "cases.json").read_text(encoding="utf-8"))["cases"]
    ok = True
    for c in cases:
        argv = ["--final", str(base / c["final"]), "--quiet"]
        if c.get("draft"):
            argv += ["--draft", str(base / c["draft"])]
        ns = _precheck_args(cs, argv)
        res = cs.run(ns)
        good = res["pass"] == c["expect_pass"]
        missing = [s for s in c.get("expect_error_contains", []) if not any(s in e for e in res["errors"])]
        extra = [s for s in c.get("expect_error_absent", []) if any(s in e for e in res["errors"])]
        fine = good and not missing and not extra
        ok &= record(f"precheck {c['id']}", fine,
                     ("" if good else f"pass={res['pass']} 期望 {c['expect_pass']}；") + (f"缺少错误片段 {missing}；" if missing else "")
                     + (f"不该出现的错误片段 {extra}；" if extra else "")
                     + ("" if fine else " 实际错误：" + " | ".join(res["errors"])[:300]))
    ns = _precheck_args(cs, ["--final", str(EXAMPLE / "03-final.md"), "--draft", str(EXAMPLE / "02-draft.md"),
                             "--claims", str(EXAMPLE / "02-claims.md"), "--html", str(EXAMPLE / "04-article.html"), "--quiet"])
    res = cs.run(ns)
    ok &= record("precheck 示例终稿通过", res["pass"], " | ".join(res["errors"]))
    ns = _precheck_args(cs, ["--final", str(EXAMPLE / "02-draft.md"), "--quiet"])
    res = cs.run(ns)
    ok &= record("precheck 示例初稿的出处覆盖完整", res["info"]["unsourced_sentences"] == 0, " | ".join(res["errors"]))
    return ok


def _precheck_args(cs, argv):
    import argparse as ap
    p = ap.ArgumentParser()
    for a in ("--final", "--draft", "--claims", "--html", "--cover-audit", "--json-out", "--report", "--package"):
        p.add_argument(a)
    for a in ("--online", "--allow-placeholders", "--quiet"):
        p.add_argument(a, action="store_true")
    return p.parse_args(argv)


# ----------------------------------------------------------------------------- humanize
def preserve_problems(original: str, edited: str, must_keep=(), must_not_add=(), max_len_ratio=None) -> list[str]:
    import check_sources as cs
    probs = []
    o_vis, e_vis = cs.strip_links(original), cs.strip_links(edited)
    on, en = set(cs.NUM_RE.findall(o_vis)), set(cs.NUM_RE.findall(e_vis))
    for n in sorted(on - en):
        probs.append(f"数字 {n} 丢失")
    for n in sorted(en - on):
        probs.append(f"新增了数字 {n}")
    oh, eh = cs.count_terms(original, cs.HEDGES), cs.count_terms(edited, cs.HEDGES)
    for t, n in oh.items():
        if eh.get(t, 0) < n:
            probs.append(f"限定词“{t}”从 {n} 处减少到 {eh.get(t, 0)} 处")
    if cs.urls_in(original) != cs.urls_in(edited):
        probs.append("链接集合发生变化")
    ofn = set(re.findall(r"\[\^[^\]]+\]", original)); efn = set(re.findall(r"\[\^[^\]]+\]", edited))
    if ofn != efn:
        probs.append(f"脚注引用变化：{sorted(ofn ^ efn)}")
    for s in must_keep:
        if s not in edited:
            probs.append(f"缺少必须保留的内容“{s}”")
    for s in must_not_add:
        if s and s in edited and s not in original:
            probs.append(f"出现了不应新增的“{s}”")
    if max_len_ratio is not None:
        ol, el = _visible_len(original), _visible_len(edited)
        if el > ol * max_len_ratio:
            probs.append(f"改后变长：{ol} → {el} 字（上限为原文的 {max_len_ratio} 倍）")
    return probs


def _visible_len(s: str) -> int:
    """去掉链接目标和空白后的字数，用来判断润色有没有把文本写长。"""
    import check_sources as cs
    return len(re.sub(r"\s+", "", cs.strip_links(s)))


def check_humanize(original=None, edited=None, outputs=None) -> bool:
    if original and edited:
        import check_sources as cs
        _, ob = cs.split_front_matter(Path(original).read_text(encoding="utf-8"))
        _, eb = cs.split_front_matter(Path(edited).read_text(encoding="utf-8"))
        ob_b, _ = cs.body_blocks(ob); eb_b, _ = cs.body_blocks(eb)
        probs = preserve_problems("\n".join(ob_b), "\n".join(eb_b))
        if cs.urls_in(ob) != cs.urls_in(eb):
            probs.append("链接集合发生变化")
        return record(f"humanize {Path(original).name} → {Path(edited).name}", not probs, "; ".join(probs))
    data = json.loads((EVALS / "humanize-cases.json").read_text(encoding="utf-8"))["cases"]
    ok = True
    if outputs:
        outs = json.loads(Path(outputs).read_text(encoding="utf-8"))
        for c in data:
            if c["id"] not in outs:
                continue
            probs = preserve_problems(c["input"], outs[c["id"]], c.get("must_keep", []), c.get("must_not_add", []),
                                      c.get("max_len_ratio"))
            ok &= record(f"humanize 输出 {c['id']}", not probs, "; ".join(probs) + ("" if not probs else f"（人工要点：{c['notes']}）"))
        return ok
    for c in data:
        args = (c.get("must_keep", []), c.get("must_not_add", []), c.get("max_len_ratio"))
        ref = preserve_problems(c["input"], c["reference_output"], *args)
        bad = preserve_problems(c["input"], c["bad_output"], *args)
        ok &= record(f"humanize 用例 {c['id']}", not ref and bool(bad),
                     ("参考答案未通过：" + "; ".join(ref) if ref else "") + ("" if bad else " 反例没有被识别"))
    ok &= check_humanize(str(EXAMPLE / "02-draft.md"), str(EXAMPLE / "03-final.md"))
    return ok


# ----------------------------------------------------------------------------- skillchange
def check_skillchange(base: str = "HEAD") -> bool:
    sys.path.insert(0, str(EVALS))
    import contextlib, io
    import check_skill_change as csc
    p = csc.build_parser()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fails = csc.selftest(p.parse_args([]))
    ok = record("skillchange 检查规则自测", not fails, "; ".join(fails))
    rep = csc.run(p.parse_args(["--all"]))
    ok &= record("skillchange 全部技能无过长正文 / 流水账", not rep, " | ".join(rep)[:400])
    rep = csc.run(p.parse_args(["--base", base]))
    ok &= record(f"skillchange 工作区 vs {base}", not rep, " | ".join(rep)[:400])
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="gzh-skills 回归检查")
    ap.add_argument("cmd", nargs="?", default="all", choices=["all", "skills", "format", "cover", "precheck", "humanize", "skillchange"])
    ap.add_argument("--original"); ap.add_argument("--edited"); ap.add_argument("--cases")
    ap.add_argument("--base", default="HEAD", help="skillchange 对比的提交")
    a = ap.parse_args(argv)
    ok = True
    if a.cmd in ("all", "skills"):
        ok &= check_skills()
    if a.cmd in ("all", "format"):
        ok &= check_format()
    if a.cmd in ("all", "cover"):
        ok &= check_cover()
    if a.cmd in ("all", "precheck"):
        ok &= check_precheck()
    if a.cmd in ("all", "humanize"):
        ok &= check_humanize(a.original, a.edited, a.cases)
    if a.cmd in ("all", "skillchange"):
        ok &= check_skillchange(a.base)
    n_fail = sum(1 for _, g, _ in RESULTS if not g)
    print(f"\n共 {len(RESULTS)} 项，失败 {n_fail} 项")
    return 0 if ok and n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
