---
name: gzh-cover
description: 需要为公众号文章做 2.35:1 头图和 1:1 分享缩略图，并自动检查文字溢出、裁剪和对比度时使用。
---

# gzh-cover：公众号封面

用 HTML 模板排版、Playwright 截图，生成头图和缩略图预览，并做确定性自检。不需要生图 key；需要插画时可以另用执行环境提供的生图工具，但插画只能作为可选背景，标题文字始终由 HTML 渲染。

## 为什么版式分两块

公众号后台上传一张封面图，再从这同一张图里分别裁出 2.35:1 头图和 1:1 缩略图（官方草稿接口文档里的 `crop_percent_list` 也是这种做法）。所以模板把画布分成：

- **左侧正方形（1:1 裁剪区）**：放 1–4 个字的“标记”，例如关键数字、缩写、一个字的栏目名。转发卡片和消息列表里只看得到它。
- **右侧主区**：kicker、标题、副标题、署名和日期，只在 2.35:1 头图里出现。

任何文字都不能跨越两块的分界线。

## 输入

一个 JSON 规格（也可以用命令行参数）：

```json
{
  "style": "swiss",
  "mark": "120",
  "kicker": "WeChat API",
  "title": "封面标题，可比文章标题短",
  "subtitle": "一句话副标题，可空",
  "byline": "账号名，可空",
  "date": "2026-10-20"
}
```

## 依赖

- Python 3.9+、`playwright`、`pillow`、`numpy`，以及 Playwright 的 Chromium（`playwright install chromium`）。
- 中文字体：Noto Sans CJK SC / Noto Serif CJK SC / Noto Sans Mono CJK SC。缺字体时截图会退回系统字体，自检照常运行，但要人工看一眼效果。

## 步骤

1. **定风格。** 读 `references/styles.md`，从 `swiss`（瑞士极简）、`editorial`（杂志编辑）、`terminal`（极客终端）里选一个。同一个账号尽量固定一个风格。
2. **写文案。**
   - 标题：最多 3 行；放不下就删字或换短说法，**不要缩小字号**。封面标题可以比文章标题短，但不能改变意思，不能出现正文没有的数字或承诺。
   - 标记：1–4 个字符，必须是文章里真实出现、且有出处的信息（数字要和正文一致）。
   - 不放未经授权的图片、他人 logo 或人物照片。
3. **渲染并自检：**

   ```bash
   .venv/bin/python skills/gzh-cover/scripts/render.py --spec cover.json --out gzh/<目录>/05-cover
   ```

   生成 `05-cover-235.png`（1800×766）、`05-cover-1x1.png`（缩略图预览，766×766）、`05-cover-source.html` 和 `05-cover-audit.json`。
4. **看自检结果。** 必须全部通过：
   - 标题不超过 3 行、副标题不超过 2 行，单行元素不横向溢出；
   - 标记完整落在 1:1 裁剪区，其他文字完整落在主区；
   - 文字离画布边缘至少 16px；
   - 字号下限：标题 28px、标记 64px、kicker 和副标题 14px（900 宽画布上的 CSS 像素）；
   - 对比度：正文 ≥4.5，24px 以上的大字 ≥3；
   - 像素检查（`scripts/audit.py`）：画面不空、缩略图区有内容、主区文字不贴上下边。
   不通过就改文案或换风格后重渲，最多三轮；仍不通过就在 `status.md` 里写明原因交给人。
5. **人工看图。** 打开两张 PNG 看一眼：有没有错字、数字是否与正文一致、缩略图里标记是否清楚。
6. **交给下一阶段。** `05-cover-audit.json` 里的 `wechat_crop_hint` 给出了在后台设置 1:1 裁剪框的位置。上传封面由人在后台手动完成。

## 单独做像素检查

```bash
.venv/bin/python skills/gzh-cover/scripts/audit.py gzh/<目录>/05-cover-235.png --crop-px 766
.venv/bin/python skills/gzh-cover/scripts/audit.py --selftest
```
