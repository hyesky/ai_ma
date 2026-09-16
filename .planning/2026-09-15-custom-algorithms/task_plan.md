# task_plan.md — ai_ma 新增自定义算法（已按用户纠正改为"记录即算法"方案）

> 工作目录：`/Users/hyexon/project/ai_ma`
> 模式：planning-with-files + ponytail
> 视觉模型：http://120.79.165.22:17044/v1（qwen/qwen3-vl-8b，av_llm id=1，**已存在**，multimodal 实测可用）

## 结论（P0 调研后，用户纠正方向）

原生设计里"自定义算法"= **av_biz_algorithm 数据记录**（像 id:2 密集人群 那样），
组合字段：flow_type(1/2/3/4) + small_model + target_labels + llm + prompt/validate + post_process(现有6种)。
**不需要改任何 Python/前端代码**。flow2/flow3 的 LLM 管线代码本来就完整，只是库里没有流2/3记录。

## 已交付（全部完成 ✅）

7 条新业务算法已插入**三处 DB**（幂等脚本 scripts/seed_biz_algorithms.py，按 name 去重）：

| id | 名称 | flow | post | 小模型 | 大模型 | 目标 |
|---|---|---|---|---|---|---|
| 3 | 人员徘徊检测 | 1 | DWELL | YOLO11n(2) | - | person |
| 4 | 遗留物品检测 | 1 | DWELL | YOLO11n(2) | - | suitcase/backpack/handbag |
| 5 | 违法停车检测 | 1 | DWELL | YOLO11n(2) | - | car/truck/bus/motorcycle |
| 6 | 通道占用检测 | 1 | DWELL | YOLO11n(2) | - | person/car/truck/bus |
| 7 | 抽烟检测 | 3 | AREA | YOLO11n(2) | qwen(1) | person（人框裁剪复核） |
| 8 | 烟火检测 | 2 | AREA | - | qwen(1) | -（全帧语义判断） |
| 9 | 物品移走检测 | 2 | AREA | - | qwen(1) | -（全帧语义判断） |

## 验证记录
- 本地 ~/project/ai_ma/ai_ma.sqlite3：✅ 9 条
- 本地 Docker 容器 /app/ai_ma.sqlite3（**线上运行实例**）：✅ 9 条
- 服务器 120.79.165.22:/opt/ai_ma/ai_ma.sqlite3（备份副本）：✅ 9 条
- Django 序列化（=web 算法列表同路径 `_biz_to_dict`）：✅ 9 条全通过，flow/后处理/小模型/大模型字段渲染正常
- LLM 视觉实测：✅ qwen3.8-27b @17044 对图片返回"正常"（qwen3 思考模式会吃 token，max_tokens 需 ≥64；管线已有余量）

## 阶段清单
- [x] P0 调研：算法记录结构 / LLM 配置 / flow2/3 管线能力 / 前端列表路径
- [x] P1 决策：确认"记录即算法"，不改代码（误改已还原）
- [x] P2 种子：scripts/seed_biz_algorithms.py 幂等脚本 + 7 条算法记录
- [x] P3 验证：三处 DB 同步、web 序列化、LLM 视觉实测
- [x] P4 交付：提交推送 GitHub，planning 收尾

## 遗留 / 可选项
- [ ] 无代码改动，容器无需重启（记录即时生效）；只在用户把算法绑定到布控区域后由管线加载
- [ ] 移走检测用 flow2 大模型语义判断（原设计能力内）；若将来要"目标先停留后消失"的精确几何判定，再议（需要代码，用户已明确不要）
- [ ] 用户消息中"抽烟算法"出现两次，判为重复，只建一个

## 如何继续增加算法（回答用户原始问题）
1. UI 方式（原设计）：算法管理 → 新增业务算法 → 填 flow/目标/后处理/大模型提示词
2. 批量方式：在 scripts/seed_biz_algorithms.py 的 ALGORITHMS 列表加一条 dict，对目标 DB 跑一遍脚本（幂等）
