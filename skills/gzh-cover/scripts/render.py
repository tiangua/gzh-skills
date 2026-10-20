#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""渲染公众号封面并做版式自检（Playwright + Chromium）。

输入一个 JSON 规格（或命令行参数），输出：
  <out>-235.png   2.35:1 头图（1800×766）
  <out>-1x1.png   1:1 缩略图预览（从头图左侧正方形裁出，766×766）
  <out>-audit.json  DOM 自检 + 像素自检结果

DOM 自检（渲染时在浏览器里量）：
  - 文本溢出：带 data-fit 的单行元素横向溢出即失败；
  - 越界：任何文字元素不能跨越 1:1 裁剪线，也不能贴边（安全边距 16px）；
  - 字号下限：正文类 ≥14px，标题 ≥28px，缩略图标记 ≥64px（CSS 像素，900 宽画布）；
  - 行数：标题最多 3 行、副标题最多 2 行（超出即判溢出）；
  - 对比度：文字与所在区块背景的 WCAG 对比度，正文 ≥4.5，24px 以上大字 ≥3。
像素自检调用同目录 audit.py。

用法：
  render.py --spec cover.json --out gzh/<目录>/05-cover
  render.py --title "标题" --mark "120" --kicker "WECHAT API" --style swiss --out /tmp/c
退出码：0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "templates" / "cover.html"
STYLES = ("swiss", "editorial", "terminal")
W, H, SCALE = 900, 383, 2
SAFE = 16
MIN_FONT = {"title": 28, "mark": 64, "kicker": 14, "subtitle": 14, "byline": 12, "date": 12}

MEASURE_JS = r"""
() => {
  const SAFE = %d;
  const crop = document.querySelector('[data-zone=crop]').getBoundingClientRect();
  function lum(c) {
    const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const [r, g, b, a] = m[1].split(',').map(Number);
    if (a === 0) return null;
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function bgOf(el) {
    while (el) { const l = lum(getComputedStyle(el).backgroundColor); if (l !== null) return l; el = el.parentElement; }
    return 1;
  }
  const out = [];
  document.querySelectorAll('[data-fit]').forEach(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const text = el.innerText.trim();
    const fg = lum(cs.color), bg = bgOf(el);
    const contrast = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
    out.push({
      role: el.dataset.role, text,
      box: [r.left, r.top, r.right, r.bottom].map(v => Math.round(v * 10) / 10),
      font: parseFloat(cs.fontSize),
      overflowX: el.scrollWidth - el.clientWidth,
      lines: (() => {
        const mh = el.style.maxHeight; el.style.maxHeight = 'none';
        const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
        const n = Math.round(el.getBoundingClientRect().height / lh);
        el.style.maxHeight = mh; return n;
      })(),
      maxLines: el.dataset.lines ? parseInt(el.dataset.lines) : null,
      inCrop: r.left >= crop.left - 0.5 && r.right <= crop.right + 0.5,
      outCrop: r.left >= crop.right - 0.5,
      contrast: Math.round(contrast * 100) / 100,
    });
  });
  return { crop: [crop.left, crop.top, crop.right, crop.bottom], items: out, W: innerWidth, H: innerHeight, SAFE };
}
""" % SAFE


def fill_template(spec: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    values = {
        "STYLE": spec.get("style", "swiss"),
        "MARK": spec.get("mark", ""),
        "KICKER": spec.get("kicker", ""),
        "TITLE": spec.get("title", ""),
        "SUBTITLE": spec.get("subtitle", ""),
        "BYLINE": spec.get("byline", ""),
        "DATE": spec.get("date", ""),
    }
    for k, v in values.items():
        tpl = tpl.replace("{{%s}}" % k, html.escape(str(v)))
    return tpl


def dom_problems(m: dict) -> list[str]:
    probs = []
    for it in m["items"]:
        role, text = it["role"], it["text"]
        if not text:
            continue
        if it["overflowX"] > 1:
            probs.append(f"{role} 横向溢出 {it['overflowX']}px：删字，不要缩小字号")
        if it["maxLines"] and it["lines"] > it["maxLines"]:
            probs.append(f"{role} 排了 {it['lines']} 行，超过上限 {it['maxLines']} 行：删字或换短标题，不要缩小字号")
        x0, y0, x1, y1 = it["box"]
        if not it["inCrop"] and not it["outCrop"]:
            probs.append(f"{role} 跨越了 1:1 裁剪线，缩略图里会被切开")
        if role == "mark" and not it["inCrop"]:
            probs.append("标记 mark 没有完整落在 1:1 裁剪区内")
        if x0 < SAFE - 0.5 and role != "mark" or y0 < SAFE - 0.5 or x1 > m["W"] - SAFE + 0.5 or y1 > m["H"] - SAFE + 0.5:
            probs.append(f"{role} 离画布边缘不足 {SAFE}px")
        need = MIN_FONT.get(role, 12)
        if it["font"] < need:
            probs.append(f"{role} 字号 {it['font']}px 低于下限 {need}px")
        need_contrast = 3.0 if it["font"] >= 24 else 4.5   # WCAG：大字 3:1，正文 4.5:1
        if it["contrast"] < need_contrast:
            probs.append(f"{role} 对比度 {it['contrast']} 低于 {need_contrast}")
    return list(dict.fromkeys(probs))


def render(spec: dict, out_prefix: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("缺少依赖：pip install playwright（Chromium 需已安装：playwright install chromium）")
    if spec.get("style", "swiss") not in STYLES:
        raise SystemExit(f"未知风格 {spec.get('style')!r}，可选：{', '.join(STYLES)}")
    warnings = []
    if not spec.get("mark"):
        spec["mark"] = str(spec.get("title", ""))[:2]
        warnings.append("没有提供 mark，已用标题前两个字代替；建议给 1–4 个字的关键词或数字")
    if len(str(spec.get("mark", ""))) > 4:
        warnings.append("mark 超过 4 个字符，缩略图里可能放不下")

    out = Path(out_prefix)
    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_name(out.name + "-source.html")
    html_path.write_text(fill_template(spec), encoding="utf-8")
    png235 = out.with_name(out.name + "-235.png")
    png11 = out.with_name(out.name + "-1x1.png")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        page.goto(html_path.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(150)
        m = page.evaluate(MEASURE_JS)
        page.screenshot(path=str(png235), full_page=False)
        crop = m["crop"]
        page.screenshot(path=str(png11), clip={"x": crop[0], "y": crop[1], "width": crop[2] - crop[0], "height": crop[3] - crop[1]})
        browser.close()

    sys.path.insert(0, str(HERE))
    import audit  # noqa: E402
    pix = audit.analyze(str(png235), crop_px=int(round((crop[2] - crop[0]) * SCALE)))
    probs = dom_problems(m) + pix["problems"]
    result = {
        "spec": spec,
        "files": {"cover_235": str(png235), "cover_1x1_preview": str(png11), "html": str(html_path)},
        "wechat_crop_hint": {
            "2.35_1": {"x1": 0, "y1": 0, "x2": 1, "y2": 1},
            "1_1": {"x1": 0, "y1": 0, "x2": round((crop[2] - crop[0]) / W, 4), "y2": 1},
            "note": "在公众号后台上传头图后，1:1 裁剪框拖到最左侧正方形即可（坐标以图片左上角为原点，0–1 比例）。",
        },
        "dom": m,
        "pixel": pix,
        "warnings": warnings,
        "problems": probs,
        "pass": not probs,
    }
    out.with_name(out.name + "-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="渲染公众号封面并自检")
    ap.add_argument("--spec", help="JSON 规格文件：style/mark/kicker/title/subtitle/byline/date")
    ap.add_argument("--out", required=True, help="输出前缀，如 gzh/<目录>/05-cover")
    for k in ("style", "mark", "kicker", "title", "subtitle", "byline", "date"):
        ap.add_argument(f"--{k}")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8")) if a.spec else {}
    for k in ("style", "mark", "kicker", "title", "subtitle", "byline", "date"):
        if getattr(a, k) is not None:
            spec[k] = getattr(a, k)
    if not spec.get("title"):
        ap.error("需要 title（--title 或 spec 里的 title）")
    r = render(spec, a.out)
    print(("✅ PASS" if r["pass"] else "❌ FAIL") + f"  {r['files']['cover_235']}")
    for w in r["warnings"]:
        print(f"  警告：{w}")
    for pr in r["problems"]:
        print(f"  问题：{pr}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
