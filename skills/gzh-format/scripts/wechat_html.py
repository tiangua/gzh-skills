#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""把 Markdown 终稿转成可直接粘贴进微信公众号编辑器的内联样式 HTML。

公众号编辑器只保留元素上的内联 style：<style>、<link>、class、<script> 都会被丢掉。
本脚本做的事：
  1. 读取 YAML front matter（title / digest / theme 等，简单键值即可）；
  2. 去掉 HTML 注释，把 Markdown 渲染成 HTML（依赖 Python-Markdown）；
  3. 按主题 JSON 给每个元素写内联 style；
  4. 外链和脚注统一改成上标编号 + 文末“参考资料”（未认证账号正文外链不可点）；
  5. 列表改成 <section> 结构（原生 ul/ol 在编辑器里渲染不稳定）；
  6. 中英文/数字之间补空格（引号内的原文引语不动，可用 --no-spacing 关闭），加粗末尾的中文标点移到加粗外；
  7. 输出合规检查结果。

做法参考 wewrite（MIT）转换器的公开思路（脚注化外链、列表转 section、标点外移），
主题样式改写自 doocs/md（WTFPL）。代码为本项目重新编写。

用法：
  wechat_html.py 03-final.md -o 04-article.html --preview 04-preview.html [--theme classic]
  wechat_html.py --check 04-article.html          # 只检查已有 HTML
  wechat_html.py --list-themes
退出码：0 = 无错误；1 = 有错误（警告不影响退出码）。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
THEMES_DIR = HERE.parent / "themes"
PREVIEW_TEMPLATE = HERE.parent / "templates" / "preview.html"

VOID = {"br", "hr", "img", "input", "meta", "link", "source", "col", "wbr"}
WECHAT_HOSTS = ("mp.weixin.qq.com", "weixin.qq.com")
CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
ZH_PUNCT = "，。、；：！？）》」』”"
LIMITS = {"title": 32, "author": 16, "digest": 120, "text_chars": 20000}
FORBIDDEN_TAGS = {"style", "script", "link", "iframe", "form", "input", "button", "object", "embed", "video", "audio"}
BAD_CSS = [r"position\s*:\s*(fixed|sticky|absolute)", r"animation", r"@keyframes", r"transform\s*:",
           r"var\(", r"color-mix\(", r"calc\(", r"filter\s*:", r"backdrop-filter"]


# ----------------------------------------------------------------------------- front matter
def split_front_matter(text: str) -> tuple[dict, str]:
    """极简 YAML 读取：只支持 `key: value`、带引号的字符串和 `- item` 列表。"""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    meta: dict = {}
    key = None
    for raw in m.group(1).splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and key:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(_unquote(item.group(1)))
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            val = kv.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [_unquote(v.strip()) for v in val[1:-1].split(",") if v.strip()]
            else:
                meta[key] = _unquote(val) if val else ""
    return meta, text[m.end():]


def _unquote(v: str) -> str:
    v = v.strip()
    v = re.sub(r"\s+#.*$", "", v) if not (v.startswith('"') or v.startswith("'")) else v
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


# ----------------------------------------------------------------------------- tiny DOM
class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag            # None = 文本节点
        self.attrs = dict(attrs or {})
        self.children: list = []
        self.parent = parent

    def text(self) -> str:
        if self.tag is None:
            return self.attrs["text"]
        return "".join(c.text() for c in self.children)


def T(text: str) -> Node:
    return Node(None, {"text": text})


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(Node(None, {"text": data}, self.cur))


def parse_html(s: str) -> Node:
    b = TreeBuilder()
    b.feed(s)
    b.close()
    return b.root


BLOCKS = {"root", "section", "blockquote", "table", "thead", "tbody", "tr", "figure", "ul", "ol", "pre"}


def serialize(n: Node) -> str:
    if n.tag in BLOCKS:
        n.children = [c for c in n.children if not (c.tag is None and not c.attrs["text"].strip())]
    if n.tag is None:
        return html.escape(n.attrs["text"], quote=False)
    inner = "".join(serialize(c) for c in n.children)
    if n.tag == "root":
        return inner
    attrs = "".join(f' {k}="{html.escape(str(v), quote=True)}"' for k, v in n.attrs.items() if v is not None)
    if n.tag in VOID:
        return f"<{n.tag}{attrs} />"
    return f"<{n.tag}{attrs}>{inner}</{n.tag}>"


# ----------------------------------------------------------------------------- theme
def load_theme(name: str) -> dict:
    p = THEMES_DIR / f"{name}.json"
    if not p.is_file():
        avail = ", ".join(sorted(x.stem for x in THEMES_DIR.glob("*.json")))
        raise SystemExit(f"找不到主题 {name!r}，可用主题：{avail}")
    theme = json.loads(p.read_text(encoding="utf-8"))
    vars_ = theme.get("vars", {})
    styles = {}
    for k, v in theme["styles"].items():
        styles[k] = re.sub(r"\{(\w+)\}", lambda m: vars_.get(m.group(1), m.group(0)), v)
    theme["resolved"] = styles
    return theme


# ----------------------------------------------------------------------------- markdown
def preprocess_markdown(md_text: str) -> tuple[str, dict]:
    """去掉 HTML 注释；把脚注定义抽出来，引用换成占位符。"""
    md_text = re.sub(r"<!--.*?-->", "", md_text, flags=re.S)
    md_text = normalize_list_indent(md_text)
    footdefs: dict[str, str] = {}

    def grab(m):
        footdefs[m.group(1)] = m.group(2).strip()
        return ""

    md_text = re.sub(r"^\[\^([^\]]+)\]:\s*(.+)$", grab, md_text, flags=re.M)
    md_text = re.sub(r"\[\^([^\]]+)\]", lambda m: f"\u2063FN{{{m.group(1)}}}\u2063", md_text)
    return md_text, footdefs


def normalize_list_indent(md_text: str) -> str:
    """Python-Markdown 要求嵌套列表缩进 4 格；常见写法是 2 格，这里统一放大。代码块内不动。"""
    out, fenced = [], False
    for line in md_text.split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        m = None if fenced else re.match(r"^( +)([-*+] |\d+[.)] )", line)
        if m and len(m.group(1)) % 4 != 0:
            line = " " * ((len(m.group(1)) + 1) // 2 * 4) + line[len(m.group(1)):]
        out.append(line)
    return "\n".join(out)


def render_markdown(md_text: str) -> str:
    try:
        import markdown  # Python-Markdown, BSD-3-Clause
    except ImportError:
        raise SystemExit("缺少依赖：pip install markdown（建议在仓库的 .venv 里安装）")
    return markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")


# ----------------------------------------------------------------------------- transforms
class Refs:
    """统一管理“参考资料”编号：同一 URL 只编一次号。"""

    def __init__(self):
        self.items: list[tuple[str, str]] = []   # (label, url)
        self.by_url: dict[str, int] = {}
        self.by_fn: dict[str, int] = {}

    def add(self, label: str, url: str) -> int:
        if url and url in self.by_url:
            return self.by_url[url]
        self.items.append((label, url))
        n = len(self.items)
        if url:
            self.by_url[url] = n
        return n


def is_wechat_link(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == h or host.endswith("." + h) for h in WECHAT_HOSTS)


def footdef_to_label_url(defn: str) -> tuple[str, str]:
    m = re.search(r"\[([^\]]+)\]\((\S+?)\)", defn)
    if m:
        rest = (defn[:m.start()] + m.group(1) + defn[m.end():]).strip()
        return rest, m.group(2)
    m = re.search(r"https?://\S+", defn)
    if m:
        label = (defn[:m.start()] + defn[m.end():]).strip(" ：:，,")
        return label or m.group(0), m.group(0).rstrip("。.,，)")
    return defn, ""


def transform(root: Node, theme: dict, footdefs: dict, warnings: list) -> Refs:
    st = theme["resolved"]
    refs = Refs()

    def sup(n: int) -> Node:
        s = Node("sup", {"style": st["sup"]})
        s.children.append(T(f"[{n}]"))
        return s

    def walk(n: Node, ctx: tuple = ()):
        new_children = []
        for c in n.children:
            if c.tag is None:
                txt = c.attrs["text"]
                if "\u2063FN{" in txt and "pre" not in ctx and "code" not in ctx:
                    parts = re.split(r"\u2063FN\{([^}]+)\}\u2063", txt)
                    for i, part in enumerate(parts):
                        if i % 2 == 0:
                            if part:
                                new_children.append(T(part))
                        else:
                            fid = part
                            if fid not in refs.by_fn:
                                if fid not in footdefs:
                                    warnings.append(f"脚注 [^{fid}] 没有定义")
                                    refs.by_fn[fid] = refs.add(f"（缺失的脚注 {fid}）", "")
                                else:
                                    label, url = footdef_to_label_url(footdefs[fid])
                                    refs.by_fn[fid] = refs.add(label, url)
                            new_children.append(sup(refs.by_fn[fid]))
                    continue
                new_children.append(c)
                continue
            walk(c, ctx + (c.tag,))
            if c.tag == "a":
                href = c.attrs.get("href", "")
                label = c.text().strip()
                if href.startswith("#"):
                    new_children.extend(c.children)       # 页内锚点在公众号里无效，保留文字
                    continue
                if href and is_wechat_link(href):
                    c.attrs = {"href": href, "style": st["a"]}
                    new_children.append(c)
                    continue
                num = refs.add(label if label and label != href else href, href)
                span = Node("span", {"style": st["a"]}) if label != href else None
                if span:
                    span.children = c.children
                    new_children.append(span)
                new_children.append(sup(num))
                continue
            new_children.append(c)
        n.children = new_children
        for c in n.children:
            c.parent = n

    walk(root)
    return refs


def restyle(root: Node, theme: dict, warnings: list) -> None:
    st = theme["resolved"]

    def conv(n: Node, depth: int = 0, in_quote: bool = False) -> list:
        if n.tag is None:
            return [n]
        tag = n.tag
        kids_quote = in_quote or tag == "blockquote"
        if tag in ("ul", "ol"):
            return convert_list(n, depth, in_quote)
        if tag == "p":
            imgs = [c for c in n.children if c.tag == "img"]
            others = [c for c in n.children if not (c.tag == "img" or (c.tag is None and not c.attrs["text"].strip()))]
            if len(imgs) == 1 and not others:
                return [make_figure(imgs[0])]
        new_kids = []
        for c in n.children:
            new_kids.extend(conv(c, depth, kids_quote))
        n.children = new_kids
        keep = {}
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            keep["style"] = st[tag]
        elif tag == "p":
            keep["style"] = st["blockquote_p"] if in_quote else st["p"]
        elif tag == "blockquote":
            keep["style"] = st["blockquote"]
        elif tag == "strong" or tag == "b":
            n.tag = "strong"
            keep["style"] = st["strong"]
        elif tag in ("em", "i"):
            n.tag = "em"
            keep["style"] = st["em"]
        elif tag in ("del", "s"):
            n.tag = "del"
            keep["style"] = st["del"]
        elif tag == "code":
            if n.parent is not None and n.parent.tag == "pre":
                return [code_block(n)]
            keep["style"] = st["code_inline"]
        elif tag == "pre":
            keep["style"] = st["pre"]
        elif tag == "table":
            keep["style"] = st["table"]
            n.attrs = keep
            wrap = Node("section", {"style": st["table_wrap"]})
            wrap.children = [n]
            return [wrap]
        elif tag in ("th", "td"):
            keep["style"] = st[tag]
            if n.attrs.get("align"):
                keep["style"] += f" text-align: {n.attrs['align']};"
        elif tag == "img":
            return [make_figure(n)]
        elif tag == "hr":
            keep["style"] = st["hr"]
        elif tag in ("a", "span", "sup"):
            keep = {k: v for k, v in n.attrs.items() if k in ("href", "style")}
        elif tag in ("thead", "tbody", "tr", "br", "section", "figure", "figcaption", "root"):
            keep = {k: v for k, v in n.attrs.items() if k == "style"}
        else:
            warnings.append(f"未识别的标签 <{tag}>，已按普通 section 输出")
            n.tag = "section"
        n.attrs = keep
        return [n]

    def make_figure(img: Node) -> Node:
        src = img.attrs.get("src", "")
        alt = img.attrs.get("alt", "")
        if not re.match(r"^https?://", src):
            warnings.append(f"图片 {src!r} 不是网络地址，粘贴后需要在编辑器里重新上传")
        fig = Node("figure", {"style": st["figure"]})
        im = Node("img", {"src": src, "alt": alt, "style": st["img"]})
        fig.children.append(im)
        if alt:
            cap = Node("figcaption", {"style": st["figcaption"]})
            cap.children.append(T(alt))
            fig.children.append(cap)
        return fig

    def code_block(code: Node) -> Node:
        text = code.text().rstrip("\n")
        c = Node("code", {"style": st["pre_code"]})
        lines = text.split("\n")
        for i, line in enumerate(lines):
            lead = len(line) - len(line.lstrip(" "))
            line = line.replace("\t", "    ")
            c.children.append(T("\u00a0" * lead + line[lead:]))
            if i < len(lines) - 1:
                c.children.append(Node("br"))
        return c

    def convert_list(lst: Node, depth: int, in_quote: bool) -> list:
        ordered = lst.tag == "ol"
        start = int(lst.attrs.get("start", 1) or 1)
        box = Node("section", {"style": st["list"] + (f" margin-left: {1.2 * depth:.1f}em;" if depth else "")})
        idx = start
        for li in [c for c in lst.children if c.tag == "li"]:
            row = Node("section", {"style": st["li"]})
            marker = Node("span", {"style": st["li_marker"]})
            marker.children.append(T(f"{idx}." if ordered else "•"))
            row.children.append(marker)
            nested = []
            for c in li.children:
                if c.tag in ("ul", "ol"):
                    nested.extend(convert_list(c, depth + 1, in_quote))
                elif c.tag == "p":
                    for g in c.children:
                        row.children.extend(conv(g, depth, in_quote))
                else:
                    row.children.extend(conv(c, depth, in_quote))
            box.children.append(row)
            box.children.extend(nested)
            idx += 1
        return [box]

    new = []
    for c in root.children:
        new.extend(conv(c))
    root.children = new


def fix_text(root: Node, spacing: bool = True) -> None:
    """中英文之间补空格（引号内的引语除外）；加粗末尾的中文标点移到加粗外。"""
    pat1 = re.compile(rf"([{CJK}])([A-Za-z0-9@#$%^&*+\-=(\[])")
    pat2 = re.compile(rf"([A-Za-z0-9%)\]!?.,;:])([{CJK}])")

    def walk(n: Node, skip: bool):
        for i, c in enumerate(list(n.children)):
            if c.tag is None:
                if not skip and spacing:
                    # 引号内是原文引语，一个字都不改
                    parts = re.split(r"(“[^”]*”|「[^」]*」|『[^』]*』)", c.attrs["text"])
                    for k in range(0, len(parts), 2):
                        t = pat1.sub(r"\1 \2", parts[k])
                        parts[k] = pat2.sub(lambda m: m.group(1) + ("" if m.group(1) in ".,;:!?" else " ") + m.group(2), t)
                    c.attrs["text"] = "".join(parts)
                continue
            walk(c, skip or c.tag in ("code", "pre"))
        # 标点外移
        out = []
        for c in n.children:
            out.append(c)
            if c.tag == "strong" and c.children and c.children[-1].tag is None:
                last = c.children[-1]
                m = re.search(rf"([{ZH_PUNCT}]+)$", last.attrs["text"])
                if m:
                    last.attrs["text"] = last.attrs["text"][: m.start()]
                    out.append(T(m.group(1)))
        n.children = out

    walk(root, False)


def append_refs(root: Node, refs: Refs, theme: dict) -> None:
    if not refs.items:
        return
    st = theme["resolved"]
    title = Node("p", {"style": st["refs_title"]})
    title.children.append(T("参考资料"))
    root.children.append(title)
    for i, (label, url) in enumerate(refs.items, 1):
        p = Node("p", {"style": st["refs_item"]})
        text = f"[{i}] {label}" + (f"：{url}" if url and url != label else (f"：{url}" if not label else ""))
        if url == label:
            text = f"[{i}] {url}"
        p.children.append(T(text))
        root.children.append(p)


# ----------------------------------------------------------------------------- check
def visible_text(fragment: str) -> str:
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", fragment)))


def check_html(fragment: str, meta: dict | None = None) -> dict:
    errors, warnings = [], []
    root = parse_html(fragment)

    def walk(n: Node):
        for c in n.children:
            if c.tag is None:
                continue
            if c.tag in FORBIDDEN_TAGS:
                errors.append(f"出现公众号不支持的标签 <{c.tag}>")
            for k, v in c.attrs.items():
                if k in ("class", "id"):
                    errors.append(f"<{c.tag}> 带有 {k} 属性，粘贴后会丢失样式")
                if k.startswith("on"):
                    errors.append(f"<{c.tag}> 带有事件属性 {k}")
                if k == "style" and v:
                    for bad in BAD_CSS:
                        if re.search(bad, v):
                            errors.append(f"<{c.tag}> 的 style 含不支持的写法：{bad}")
            if c.tag == "a":
                href = c.attrs.get("href", "")
                if href and not is_wechat_link(href):
                    warnings.append(f"正文含外链 {href}：未认证账号不可点击，建议改为参考资料编号")
            if c.tag == "img":
                src = c.attrs.get("src", "")
                if not src.startswith("http"):
                    warnings.append(f"图片 {src!r} 不是网络地址，粘贴后需要在编辑器里重新上传")
            walk(c)

    walk(root)
    text = visible_text(fragment)
    stats = {"html_chars": len(fragment), "text_chars": len(text)}
    if stats["text_chars"] >= LIMITS["text_chars"]:
        errors.append(f"正文 {stats['text_chars']} 字，超过公众号 2 万字上限")
    if stats["html_chars"] >= LIMITS["text_chars"]:
        warnings.append(f"HTML 共 {stats['html_chars']} 字符（含标签）。手动粘贴不受影响；若以后走官方草稿接口，content 需少于 2 万字符")
    if meta:
        for key in ("title", "author", "digest"):
            val = str(meta.get(key) or "")
            if key == "title" and not val:
                errors.append("front matter 缺少 title")
            if len(val) > LIMITS[key]:
                errors.append(f"{key} 共 {len(val)} 字，超过上限 {LIMITS[key]} 字")
        if not meta.get("digest"):
            warnings.append("没有 digest：公众号会默认抓取正文前 54 个字作摘要")
    # 去重
    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}


# ----------------------------------------------------------------------------- main
def convert(md_text: str, theme_name: str | None = None, spacing: bool = True) -> tuple[str, dict, dict, list]:
    meta, body = split_front_matter(md_text)
    theme = load_theme(theme_name or meta.get("theme") or "classic")
    warnings: list[str] = []
    body, footdefs = preprocess_markdown(body)
    # 正文开头若是与 title 相同的一级标题，去掉（公众号标题单独填写）
    title = str(meta.get("title") or "")
    if title:
        body = re.sub(rf"^\s*#\s+{re.escape(title)}\s*\n", "", body, count=1)
    raw = render_markdown(body)
    root = parse_html(raw)
    refs = transform(root, theme, footdefs, warnings)
    restyle(root, theme, warnings)
    fix_text(root, spacing)
    append_refs(root, refs, theme)
    # 去掉块之间的纯空白文本节点
    root.children = [c for c in root.children if not (c.tag is None and not c.attrs["text"].strip())]
    container = Node("section", {"style": theme["resolved"]["container"]})
    container.children = root.children
    fragment = serialize(container)
    return fragment, meta, theme, warnings


def build_preview(fragment: str, meta: dict, report: dict, theme: dict) -> str:
    tpl = PREVIEW_TEMPLATE.read_text(encoding="utf-8")
    rep = {
        "{{TITLE}}": html.escape(str(meta.get("title") or "（无标题）")),
        "{{DIGEST}}": html.escape(str(meta.get("digest") or "（无摘要）")),
        "{{THEME}}": html.escape(theme.get("label", theme["name"])),
        "{{STATS}}": html.escape(f"正文 {report['stats']['text_chars']} 字 · 错误 {len(report['errors'])} · 警告 {len(report['warnings'])}"),
        "{{ARTICLE}}": fragment,
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)
    return tpl


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Markdown → 公众号内联样式 HTML")
    ap.add_argument("input", nargs="?", help="Markdown 终稿")
    ap.add_argument("-o", "--output", help="输出 HTML 片段（粘贴用）")
    ap.add_argument("--preview", help="输出本地预览页（带复制按钮）")
    ap.add_argument("--theme", help="主题名，默认取 front matter 的 theme，否则 classic")
    ap.add_argument("--check", metavar="HTML", help="只检查一个已有的 HTML 片段")
    ap.add_argument("--json", action="store_true", help="检查结果用 JSON 输出")
    ap.add_argument("--list-themes", action="store_true")
    ap.add_argument("--no-spacing", action="store_true", help="不在中英文之间自动补空格")
    a = ap.parse_args(argv)

    if a.list_themes:
        for p in sorted(THEMES_DIR.glob("*.json")):
            t = json.loads(p.read_text(encoding="utf-8"))
            print(f"{t['name']:<10} {t.get('label', '')}  {t.get('description', '')}")
        return 0
    if a.check:
        report = check_html(Path(a.check).read_text(encoding="utf-8"))
        _print_report(report, a.json)
        return 0 if report["ok"] else 1
    if not a.input:
        ap.error("需要输入 Markdown 文件")
    md_text = Path(a.input).read_text(encoding="utf-8")
    fragment, meta, theme, conv_warn = convert(md_text, a.theme, spacing=not a.no_spacing)
    report = check_html(fragment, meta)
    report["warnings"] = list(dict.fromkeys(conv_warn + report["warnings"]))
    report["theme"] = theme["name"]
    out = Path(a.output) if a.output else Path(a.input).with_suffix(".html")
    out.write_text(fragment + "\n", encoding="utf-8")
    report["output"] = str(out)
    if a.preview:
        Path(a.preview).write_text(build_preview(fragment, meta, report, theme), encoding="utf-8")
        report["preview"] = a.preview
    _print_report(report, a.json)
    return 0 if report["ok"] else 1


def _print_report(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(("✅ 通过" if report["ok"] else "❌ 有错误") + f"  正文 {report['stats']['text_chars']} 字，HTML {report['stats']['html_chars']} 字符")
    for e in report["errors"]:
        print(f"  错误：{e}")
    for w in report["warnings"]:
        print(f"  警告：{w}")
    if report.get("output"):
        print(f"  输出：{report['output']}")
    if report.get("preview"):
        print(f"  预览：{report['preview']}")


if __name__ == "__main__":
    sys.exit(main())
