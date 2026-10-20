---
stage: 2-claims
example: true
topic: "公众号摘要上限 120 字"
---

## 任务书

- 目标读者：自己写脚本或用开源工具排版、推送公众号文章的运营和开发者
- 阅读情境：维护写稿 / 排版工具，或者准备接入官方草稿接口
- 读者的问题：工具里的长度检查还对吗？
- 读完的结论：长度检查以官方文档为准：标题 32、作者 16、摘要 120
- 读完的行动 / 判断方法：照文末清单核对自己的工具
- 核心判断：第三方资料里的旧写法可能让工具超限，检查值应直接引用官方文档并注明查阅日期
- 新增价值：把分散的限制和变更日志放在一起，指出资料不一致
- 成立边界：只针对接口文档；后台编辑器以后台提示为准；未实测接口报错
- 最强反方：手动发布的人不调接口，影响很小
- 个人材料：无

## 对照表

| ID | 论点（正文准备怎么说） | 类型 | 证据要点 | 出处 | 状态 | 限定词 / 边界 |
|---|---|---|---|---|---|---|
| C1 | 摘要总长度不超过 120 个字 | 事实 | 参数表 digest 一行 | [新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html) | 已核实 | 原文“总长度不超过120个字” |
| C2 | 变更日志：2026-07-14“api摘要长度限制对齐mp端120字” | 事实 | 页面底部“接口变更日志” | [新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html) | 已核实 | 日志没有写旧值 |
| C3 | 此前接口的摘要上限与后台不一致 | 推断 | 依据 C2 的“对齐”二字 | — | 已核实 | 正文写“从措辞看……可能” |
| C4 | 第三方说明写着摘要最多 128 个字符 | 事实 | 参数表 digest 一行 | [HuanCode Docs](https://docs.huancode.com/blog/wechat-draft-add-api) | 已核实 | 只说明资料不一致，不说它是旧值 |
| C5 | 标题 ≤32 字，作者 ≤16 字；单图文才有摘要，不填取正文前 54 字 | 事实 | 参数表 title / author / digest | [新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html) | 已核实 | |
| C6 | 正文少于 2 万字符、小于 1M，去除 JS，外部图片 URL 被过滤 | 事实 | 参数表 content 一行 | [新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html) | 已核实 | |
| C7 | 旧的接口上限就是 128 字 | 事实 | 官方文档没有写旧值 | — | 待核实 | 不进正文 |

## 段落与论点对应
- 开头：C1
- 发生了什么：C2、C3、C4、C5
- 对写稿流程意味着什么：C4、C1、C6，作者判断
- 边界：任务书的边界
- 可以怎么做：C1、C5、C6
