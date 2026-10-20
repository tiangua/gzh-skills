#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""封面 PNG 的像素级自检。

逐行“横向边缘密度”判断一行有没有内容（文字、线条有边缘，纯色和平滑渐变没有）。
该检测方法改写自 ZJU-REAL/Easel 的 skills/builtin/card-design/scripts/card_audit.py
（Apache-2.0），阈值和判定规则按公众号封面重新设定：

  - 整张图不能近乎空白（有内容的行 ≥ 15%）；
  - 1:1 裁剪区（左侧正方形）必须有内容，否则缩略图是一块纯色；
  - 主区（裁剪区右侧）必须有内容；
  - 内容不能贴到上下边缘（顶部、底部 2% 内出现内容视为贴边）。

用法：
  audit.py cover-235.png [--crop-px 766] [--json]
  audit.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EDGE_TOL = 12
ROW_EDGE_FRAC = 0.006


def _rows_with_content(arr):
    import numpy as np
    gray = arr.mean(axis=2)
    edge = np.abs(np.diff(gray, axis=1)) > EDGE_TOL
    return edge.mean(axis=1) > ROW_EDGE_FRAC


def analyze(path: str, crop_px: int | None = None) -> dict:
    import numpy as np
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    arr = np.asarray(img).astype("int16")
    crop_px = crop_px or h
    problems = []

    ratio = w / h
    if abs(ratio - 2.35) > 0.03:
        problems.append(f"画幅比例 {ratio:.3f}，不是 2.35:1")

    rows = _rows_with_content(arr)
    fill = float(rows.mean())
    if fill < 0.15:
        problems.append(f"有内容的行只占 {fill:.0%}，画面近乎空白")

    crop_px = min(crop_px, w - 8)
    crop_rows = _rows_with_content(arr[:, :crop_px])
    main_rows = _rows_with_content(arr[:, crop_px + 4:])
    if crop_rows.mean() < 0.05:
        problems.append("1:1 裁剪区没有内容，缩略图会是一块纯色")
    if main_rows.mean() < 0.10:
        problems.append("主区没有足够内容（标题可能没渲染出来）")

    band = max(1, int(h * 0.02))
    if main_rows[:band].any() or main_rows[-band:].any():
        problems.append("主区文字贴到了上下边缘")

    return {
        "file": str(path), "size": f"{w}x{h}", "fill": round(fill, 3),
        "crop_fill": round(float(crop_rows.mean()), 3), "main_fill": round(float(main_rows.mean()), 3),
        "problems": problems, "pass": not problems,
    }


def _selftest() -> int:
    import tempfile
    import numpy as np
    from PIL import Image
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(f"[{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    with tempfile.TemporaryDirectory() as td:
        w, h = 1800, 766
        good = np.full((h, w, 3), 245, np.uint8)
        good[200:560, 100:660][:, ::6] = 20      # 裁剪区标记
        good[120:640, 900:1700][:, ::6] = 20     # 主区标题
        f = Path(td) / "good.png"; Image.fromarray(good).save(f)
        chk("正常封面通过", analyze(str(f), 766)["pass"])

        blank_crop = good.copy(); blank_crop[:, :766] = 245
        f = Path(td) / "nocrop.png"; Image.fromarray(blank_crop).save(f)
        chk("检出缩略图区空白", not analyze(str(f), 766)["pass"])

        edge = good.copy(); edge[0:10, 900:1700][:, ::6] = 20
        f = Path(td) / "edge.png"; Image.fromarray(edge).save(f)
        chk("检出贴边", not analyze(str(f), 766)["pass"])

        sq = np.full((800, 800, 3), 245, np.uint8)
        f = Path(td) / "sq.png"; Image.fromarray(sq).save(f)
        chk("检出比例错误", not analyze(str(f))["pass"])
    print("✅ selftest 通过" if ok else "❌ selftest 失败")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="封面 PNG 像素自检")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--crop-px", type=int)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.file:
        ap.error("需要 PNG 文件")
    r = analyze(a.file, a.crop_px)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(("✅ PASS" if r["pass"] else "❌ FAIL") + f"  {r['file']} ({r['size']})")
        for p in r["problems"]:
            print(f"  问题：{p}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
