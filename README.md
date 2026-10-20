# gzh-skills

**English:** Agent skills (SKILL.md) for producing WeChat Official Account (公众号) articles from a sourced news brief — topic picking, drafting with a claims table, de-AI-ifying Chinese prose, inline-styled HTML formatting, cover rendering and a pre-publish check — with manual publishing only.

一套给 AI agent 用的公众号写作技能：从一份带链接的资讯简报出发，经过选题、写稿、去 AI 腔、排版、封面、发布前检查，产出一个**由人手动发布**的发布包。每个技能是一个 `SKILL.md`，任何支持这种格式的 agent 都能直接读取执行，不需要另配大模型 key。

## 硬性规则

- **只做手动发布。** 不调用任何群发 / 发布接口，流程终点是交给人的发布包。
- **不扫码登录，不用非官方接口。** 不驱动已登录的公众号后台，不抓包调用未公开接口。
- **每条事实都带出处链接。** 查不到出处就删掉或改写成明确的推断。
- **不把含糊说法改成确定说法。** “可能 / 据称 / 计划 / 尚未 / 约 / 超过”原样保留，脚本会对比初稿和终稿。

## 流程

```
简报（带链接）
  │  gzh-topic-pick   挑 1–3 个选题，评分，给“做 / 改方向 / 不做”
  ▼
选题卡
  │  gzh-draft        任务书 + 论点–证据–出处对照表 + Markdown 初稿
  ▼
初稿
  │  zh-humanize      去 AI 腔，保住事实、限定词和链接
  ▼
终稿 ──┬── gzh-format  → 可粘贴的内联样式 HTML + 预览页
       └── gzh-cover   → 2.35:1 头图 + 1:1 缩略图 + 自检
  │  gzh-precheck     脚本检查 + 人工核对 → 通过才打出发布包
  ▼
人在公众号后台粘贴、上传封面、点发布
```

`gzh-pipeline` 管整条流程：每篇文章一个 `gzh/<日期>-<slug>/` 目录，规定每一步交付什么文件、状态怎么记、失败怎么重跑。

## 技能清单

| 技能 | 什么时候用 | 脚本 |
|---|---|---|
| [`gzh-pipeline`](skills/gzh-pipeline/SKILL.md) | 从简报出发按阶段做一篇文章 | — |
| [`gzh-topic-pick`](skills/gzh-topic-pick/SKILL.md) | 从简报里挑选题并评分 | — |
| [`gzh-draft`](skills/gzh-draft/SKILL.md) | 根据选题卡写带对照表的初稿 | — |
| [`zh-humanize`](skills/zh-humanize/SKILL.md) | 去中文 AI 腔，不动事实 | — |
| [`gzh-format`](skills/gzh-format/SKILL.md) | Markdown → 公众号可粘贴 HTML | `scripts/wechat_html.py` |
| [`gzh-cover`](skills/gzh-cover/SKILL.md) | 做头图和缩略图并自检 | `scripts/render.py`、`scripts/audit.py` |
| [`gzh-precheck`](skills/gzh-precheck/SKILL.md) | 发布前把关、打发布包 | `scripts/check_sources.py` |

## 安装

**作为技能使用：** 把 `skills/` 下的各个文件夹拷进 agent 的技能库（每个文件夹一个技能，入口是 `SKILL.md`）。技能之间用名字互相引用，建议七个一起安装。

**运行脚本：** 需要 Python 3.9+。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # 只有 gzh-cover 需要；已装过 Chromium 可跳过
```

中文字体建议安装 Noto Sans CJK SC / Noto Serif CJK SC。

## 示例与测试

- [`examples/2026-10-20-digest-limit/`](examples/2026-10-20-digest-limit/)：一份完整示例，从构造的简报条目到手动发布包。示例里的事实来自微信官方文档，已核对；署名为虚构的“示例账号”。
- `evals/`：
  - `humanize-cases.json`：`zh-humanize` 的边界用例（不补数字、不丢限定词、不改引语……）；
  - `precheck-cases/`：故意埋了问题的稿件（缺出处、绝对化标题、“可能”变“确定”、新增数字、占位链接）；
  - `run_checks.py`：一键跑全部脚本类检查。

```bash
.venv/bin/python evals/run_checks.py            # 全部
.venv/bin/python evals/run_checks.py humanize --original 02-draft.md --edited 03-final.md
bash examples/2026-10-20-digest-limit/rebuild.sh   # 重新生成示例产物
```

## 目录结构

```
gzh-skills/
├── README.md  LICENSE  NOTICE  CREDITS.md  requirements.txt
├── third_party_licenses/      # 改写来源的许可证原文
├── skills/
│   ├── gzh-pipeline/          SKILL.md, references/handoff-format.md
│   ├── gzh-topic-pick/        SKILL.md, references/scoring.md
│   ├── gzh-draft/             SKILL.md, templates/article.md, references/claims-table.md
│   ├── zh-humanize/           SKILL.md, references/patterns.md
│   ├── gzh-format/            SKILL.md, scripts/wechat_html.py, themes/{classic,grace}.json, templates/preview.html
│   ├── gzh-cover/             SKILL.md, references/styles.md, templates/cover.html, scripts/{render,audit}.py
│   └── gzh-precheck/          SKILL.md, references/checklist.md, scripts/check_sources.py
├── examples/2026-10-20-digest-limit/
└── evals/                     humanize-cases.json, precheck-cases/, run_checks.py
```

## 许可证与来源

Apache-2.0。部分内容改写自 ZJU-REAL/Easel（Apache-2.0）、op7418/Humanizer-zh（MIT）、wewrite（MIT）、doocs/md（WTFPL），逐项说明见 [CREDITS.md](CREDITS.md) 和 [NOTICE](NOTICE)。AGPL 等许可的项目只借鉴思路，本仓库不含它们的任何文字或代码。

## 后续计划

- `brief-video`：把简报做成一分钟带配音的讲解视频
- `gzh-style-learn`：从人改过的稿子里学写作偏好
- `xhs-carousel`：同一篇内容转成小红书组图
- `gzh-review`：发布后复盘（阅读数据由人手动提供）
