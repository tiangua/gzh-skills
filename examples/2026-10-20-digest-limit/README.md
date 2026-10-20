# 示例：从简报条目到手动发布包

> **这是演示用的示例内容**，用来展示 `gzh-pipeline` 每个阶段的交付物长什么样。署名“示例账号”是虚构的。
>
> 文中事实全部来自两个公开页面，已于 2026-10-20 打开核对：
> - 微信公众号文档《新增草稿》：https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html
> - HuanCode Docs《微信公众号草稿箱 API：新增草稿 (draft/add)》：https://docs.huancode.com/blog/wechat-draft-add-api
>
> `00-brief.md` 是按资讯简报格式**手工构造**的一条，不是真实简报的输出。页面以后可能更新，复用前请重新核对。

| 文件 | 阶段 | 由谁生成 |
|---|---|---|
| `00-brief.md` | 0 简报（构造） | 手写 |
| `status.md` | 流程状态 | `gzh-pipeline` |
| `01-topic-card.md` | 1 选题 | `gzh-topic-pick` |
| `02-draft.md`、`02-claims.md` | 2 初稿与对照表 | `gzh-draft` |
| `03-final.md`、`03-humanize-notes.md` | 3 去 AI 腔 | `zh-humanize` |
| `04-article.html`、`04-preview.html` | 4 排版 | `gzh-format/scripts/wechat_html.py` |
| `cover.json`、`05-cover-*` | 5 封面 | `gzh-cover/scripts/render.py` |
| `06-precheck.md`、`06-precheck.json`、`package/` | 6 发布前检查 | `gzh-precheck/scripts/check_sources.py` |

重新生成脚本产物（在仓库根目录）：

```bash
bash examples/2026-10-20-digest-limit/rebuild.sh
```
