---
name: gzh-format
description: 需要把 Markdown 终稿转成能直接粘贴进微信公众号编辑器的内联样式 HTML（并生成本地预览页）时使用。
---

# gzh-format：Markdown → 公众号可粘贴 HTML

公众号编辑器只保留元素上的内联 `style`，`<style>`、`class`、`<script>`、外部 CSS 都会被丢掉；未认证账号的正文外链也不可点击。本技能用一个确定性脚本完成转换，不需要任何 key，也不连接公众号后台。

## 输入与输出

- 输入：终稿 Markdown（通常是 `03-final.md`），front matter 里可以写 `title`、`digest`、`author`、`theme`。
- 输出：
  - `04-article.html`：只含一个带内联样式的 `<section>`，用来粘贴；
  - `04-preview.html`：本地预览页，模拟手机宽度，带“复制正文”按钮，显示字数和检查结果。

## 依赖

- Python 3.9+，以及 `markdown`（Python-Markdown）。在仓库根目录执行一次：

  ```bash
  python3 -m venv .venv && .venv/bin/pip install markdown
  ```

## 步骤

1. **确认终稿已过 `zh-humanize`。** 排版不改文字。发现错字或事实问题，退回上一阶段修改，不在 HTML 里手改。
2. **选主题。** 运行 `scripts/wechat_html.py --list-themes` 查看。现有：
   - `classic`：居中标题、主题色底二级标题，适合解读和资讯；
   - `grace`：圆角标题块、虚线三级标题，适合观点和方法。
   同一个账号尽量固定一个主题。front matter 的 `theme` 优先，命令行 `--theme` 可以覆盖。
3. **转换：**

   ```bash
   .venv/bin/python skills/gzh-format/scripts/wechat_html.py gzh/<目录>/03-final.md \
     -o gzh/<目录>/04-article.html --preview gzh/<目录>/04-preview.html
   ```

   脚本会：
   - 去掉 HTML 注释和与 `title` 重复的一级标题（公众号标题单独填写）；
   - 把外链和脚注统一改为上标 `[n]`，在文末生成“参考资料”列表，同一 URL 只编一个号；指向 `mp.weixin.qq.com` 的链接保留为可点链接；
   - 把列表改成 `<section>` 结构，代码块换行和缩进改成 `<br>` 和不换行空格；
   - 在中文与英文、数字之间补空格（弯引号和「」里的原文引语保持原样；不想要可加 `--no-spacing`），把加粗末尾的中文标点移到加粗外；
   - 输出检查结果。
4. **看检查结果。** 有“错误”就必须修：不支持的标签或属性、正文超过 2 万字、标题超过 32 字、摘要超过 120 字、作者超过 16 字（上限来自公众号官方草稿接口文档）。“警告”逐条判断，例如本地图片需要在编辑器里重新上传。
5. **打开预览页检查。** 用浏览器打开 `04-preview.html`，看标题层级、列表、表格、代码块和参考资料。需要截图时可用 Playwright 截取 `#article` 区域。
6. **交给下一阶段。** 不在这里粘贴到公众号后台，也不调用任何接口。粘贴发布由人在 `gzh-precheck` 通过后手动完成。

## 单独检查一个 HTML

```bash
.venv/bin/python skills/gzh-format/scripts/wechat_html.py --check some.html --json
```

## 加新主题

在 `themes/` 下新建 JSON，结构同 `classic.json`：`vars` 放颜色和字体，`styles` 用 `{变量名}` 引用。只写公众号支持的属性：不要用 `var()`、`calc()`、`color-mix()`、`position: fixed`、动画和 `transform`，检查脚本会把它们当作错误。主题来源要在 `source` 字段写清楚；只能改写许可证允许的项目。
