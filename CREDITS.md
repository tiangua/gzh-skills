# 来源与致谢

本仓库只收录许可证允许改写的内容，并在这里逐项写明来源、许可证和改写方式。“只借鉴思路”的项目，本仓库不含它们的任何文字或代码。

各来源的许可证均在本地克隆中打开 LICENSE 文件核对过（2026-10-20）；核对时的提交如下。

## 一、改写收录（保留署名）

| 来源 | 许可证（已核对） | 核对的提交 | 改写到哪里 | 改写了什么 |
|---|---|---|---|---|
| [ZJU-REAL/Easel](https://github.com/ZJU-REAL/Easel) | Apache-2.0 | `8d08b21` | `skills/gzh-topic-pick/references/scoring.md` | 选题评分维度、标尺、加权方法（来自 `skills/shared/scoring-dimensions.md`）。去掉“变现潜力”，新增“出处可靠”及一票否决，重配权重 |
| 同上 | 同上 | 同上 | `skills/gzh-draft/SKILL.md` | 文章结构与开头写法的思路（`skill-article-outline`、`skill-hook-generator`）。只保留有出处的数字开头、反常识开头、问题开头；去掉“个人蜕变”“自我坦白”等需要个人经历的写法 |
| 同上 | 同上 | 同上 | `skills/zh-humanize/references/patterns.md` 第七节 | 部分中文 AI 腔词表（`text-polisher/references/zh-ai-markers.md`）。未采用其中“注入第一手细节”的做法，因为与“不编造”冲突 |
| 同上 | 同上 | 同上 | `skills/gzh-cover/references/styles.md`、`templates/cover.html` | 瑞士极简、杂志编辑、极客终端三种风格的配色与字体规格，“字越大越细”“放不下就删字”等排版规则（`card-design/references/styles.md`、`typography.md`、`layout-laws.md`） |
| 同上 | 同上 | 同上 | `skills/gzh-cover/scripts/audit.py` | 逐行横向边缘密度判断“有没有内容”的检测方法（`card-design/scripts/card_audit.py`）。阈值和判定规则按封面重写，代码重新编写 |
| 同上 | 同上 | 同上 | `skills/gzh-precheck/references/checklist.md`、`SKILL.md` | 发布前检查维度：完整性、绝对化用语、虚假宣传、版权（`skill-publish-checklist`、`skill-quality-gate/references/general-rules.md`、`skill-risk-scanner`） |
| [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh) | MIT | `f4518a8` | `skills/zh-humanize/SKILL.md`、`references/patterns.md` | 编辑约束的优先级、工作流程、受保护内容、31 类模式的分类与处理原则。全部用本项目语境重写，示例换成新的 |
| 同上 | 同上 | 同上 | `evals/humanize-cases.json` | 4 条用例的输入改写自其 `tests/fixtures/cases.json`（每条标注 `adapted_from`），其余 8 条为原创 |
| Humanizer-zh 的上游 [blader/humanizer](https://github.com/blader/humanizer)、[hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) | MIT（GitHub 许可证接口核对） | — | 同上 | 经由 Humanizer-zh 间接继承的分类思路 |
| [wewrite](https://github.com/imraywang/wewrite) | MIT | `220db1d` | `skills/gzh-draft/references/claims-table.md`、`SKILL.md` | “文章任务书 + 主张清单”、个人材料边界、事实/推断/观点分开（`wewrite-write/references/article-brief.md`、`editorial-quality.md`） |
| 同上 | 同上 | 同上 | `skills/gzh-pipeline/SKILL.md` | 阶段划分、每篇独立目录、失败只重做失败阶段（`skills/wewrite/SKILL.md`） |
| 同上 | 同上 | 同上 | `skills/gzh-format/scripts/wechat_html.py` | 外链转脚注编号、列表转 section、加粗后标点外移、中英文补空格这几个处理点（`wewrite-publish/references/wechat-constraints.md` 的说明）。代码重新编写 |
| 同上 | 同上 | 同上 | `skills/gzh-precheck/SKILL.md` | “逐项对到来源、查不到就删除或缩小”的审稿做法（`wewrite-review`） |
| [Nanako0129/sepia](https://github.com/Nanako0129/sepia) | MIT | `fb06be7` | `skills/zh-humanize/SKILL.md` 步骤 2、4 | 结构检查：首句连读（outline test）、每段回答什么问题（QUD 检查，至少一段做对比或核实）、中段有开头没预告的信息、结尾不复述（`skills/sepia/references/discourse-pass.md` §1–2、`professional-pass.md` 第 7 项）；删除测试与回退测试（`style-pass.md` §4 末段）；“每篇只挑 3–5 处”的选择原则（`SKILL.md` Calibration）。全部用中文重写，不设数字阈值。未采用 `languages/zh.md` 的标点、数字规则，因其以台湾繁体为准，不适用于简体 |
| 同上 | 同上 | 同上 | `skills/gzh-draft/SKILL.md` 步骤 3–5、`templates/article.md`、`references/claims-table.md` | 把固定的“是什么 → 为什么重要 → 怎么做 → 结论”问题序列视为机器结构；从具体问题开头；至少一个写明不成立条件的判断；篇幅按内容分配（`references/domains/tech-articles.md` 规则 1–3、5） |
| 同上 | 同上 | 同上 | `evals/humanize-cases.json` | 3 条“润色后变长变空”用例（`padding_already_plain`、`revert_shorter_word`、`nominalization_padding`）依据删除 / 回退测试的思路原创，未复制 sepia 的用例 |
| [doocs/md](https://github.com/doocs/md) | WTFPL | `f8d9126` | `skills/gzh-format/themes/classic.json`、`grace.json` | `default.css`、`grace.css` 的标题、段落、引用、表格等样式；默认字体栈和主题色。CSS 变量展开为固定值，去掉阴影和公众号不支持的写法 |

## 二、只借鉴思路（本仓库不含其任何文字或代码）

| 来源 | 许可证 | 借鉴了什么 |
|---|---|---|
| [op7418/guizang-social-card-skill](https://github.com/op7418/guizang-social-card-skill) | AGPL-3.0 | 封面“渲染后自动检查溢出”的做法。本仓库的检查项和代码独立设计（Easel 的 card-design 也注明只借鉴了它的思路） |
| [op7418/guizang-product-video-skill](https://github.com/op7418/guizang-product-video-skill) | AGPL-3.0 | v1 未使用。计划中的 `brief-video` 会参考其新闻讲解视频的流程思路，届时全部自行编写 |
| [op7418/guizang-material-illustration](https://github.com/op7418/guizang-material-illustration) | 无 LICENSE 文件 | v1 未使用 |
| [isjiamu/gzh-design-skill](https://github.com/isjiamu/gzh-design-skill)（含 Easel 内的 `gzh-design` 副本） | AGPL-3.0 | 公众号排版“只能用内联样式”的约束思路。没有使用其任何模板或样式 |
| [geekjourneyx/md2wechat-skill](https://github.com/geekjourneyx/md2wechat-skill) | 源码可见许可（BSL 1.1 衍生） | 终稿 front matter 携带标题、摘要等元数据的思路。长度上限改为直接引用微信官方文档 |
| [doniyor117/no-ai-slop](https://github.com/doniyor117/no-ai-slop)（核对提交 `52b8051`） | MIT；其模式清单改编自维基百科 “Signs of AI writing”，为 CC BY-SA 4.0 | “换个对象还成立吗”“是不是读者都知道”两个测试，用于 `gzh-draft` 写正文和自查、`gzh-topic-pick` 判断新增价值。中文规则自行编写，未收录其 36 条模式清单的任何文字；未采纳其“绝对不用破折号”的规则（与 `zh-humanize` 不机械删破折号的原则冲突） |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 技能文档（[Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)） | 项目为 MIT；只参考了公开文档 | “记教训，不记日志”的技能写法（规则 + 一句原因，挂在受影响的步骤上，不写事故经过、编号、日期、聊天原话）；技能写入先暂存、人批准后才落地（write_approval）；正文过长、参考文件过多、编号堆积的提示型检查。`docs/skill-evolution.md` 和 `evals/check_skill_change.py` 为本项目自行编写，阈值按本仓库规模另定 |
| [xiaohuailabs/xiaohu-wechat-format](https://github.com/xiaohuailabs/xiaohu-wechat-format) | README 写 MIT，但没有 LICENSE 文件 | Markdown 转公众号 HTML 的一般思路 |

## 三、没有使用

- **[iniwap/AIWriteX](https://github.com/iniwap/AIWriteX)**（Apache-2.0）：其 NOTICE 附加了“未经书面授权禁止分发衍生作品”的条款，本仓库不含任何来自它的内容。
- **Easel `skill-news-intelligence`**：Easel 注明移植自其他项目，上游许可未核实，未使用。
- **wenyan-mcp**（Apache-2.0）：可以改写，但它的主题样式在独立的 `@wenyan-md/core` 包里，本地没有核对该包的许可证，v1 未使用。

## 四、事实来源

公众号标题、作者、摘要和正文长度上限引自微信公众号文档《新增草稿》：
https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html （2026-10-20 查阅）
