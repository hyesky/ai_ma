# progress.md — ai_ma 自定义算法扩展（已完成）

## 会话日志

### 2026-09-15
- 用户问：项目有几个自定义算法？如何增加？
- 用户纠正方向：**不要改现有代码**，按原设计 = 业务算法数据记录（如 id:2 密集人群）
- 已还原误改的 models.py / biz_rules.py / pipeline.py（git checkout，确认无残留）
- 调研确认：av_llm 已有 qwen/qwen3-vl-8b(id=1) @120.79.165.22:17044；flow2/3 管线代码完整但库中无流2/3记录
- 交付：scripts/seed_biz_algorithms.py（幂等）新增 7 条业务算法，三处 DB 全部同步
- 验证：web 序列化 9 条通过；LLM 视觉实测返回正常（qwen3 思考模式吃 token 已确认）
- 已提交并推送 GitHub hyesky/ai_ma（commit 2f6dd8d）

### 2026-09-15（第二批）
- 用户追加 43 个算法清单；去重 3 条（口罩检测=戴口罩检测 / 人员徘徊=已有 / 吸烟检测=抽烟检测）→ 新增 40 条
- 实现策略：COCO-80 目标用 flow1（DWELL/LINE_COUNT/DENSITY/DIRECTION/AREA/LINE_CROSS）；非 COCO 物体与整体语义用 flow2（qwen 全帧）；PPE 穿戴/人的动作用 flow3（YOLO 检出 person → qwen 复核）
- 三处 DB 全部 49 条；web 序列化抽查通过（post/flow 分布正确）；commit ce733f5 已推送

## 测试记录
| 项目 | 结果 |
|---|---|
| 本地 ~/project/ai_ma/ai_ma.sqlite3（9条） | ✅ |
| 本地 Docker 容器 /app/ai_ma.sqlite3（线上实例，9条） | ✅ |
| 服务器 /opt/ai_ma/ai_ma.sqlite3（备份，9条） | ✅ |
| Django `_biz_to_dict` 序列化（web 列表同路径） | ✅ 全通过 |
| LLM 视觉调用（17044 qwen3.8-27b） | ✅ 返回"正常" |
| 幂等性（脚本可重复运行） | ✅ skip 已存在 |
