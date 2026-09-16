# findings.md — ai_ma 自定义算法扩展

## 系统现状（本地 DB 与服务器 DB 一致）
- 业务算法 `av_biz_algorithm`：仅 2 条
  1. 人员区域入侵（flow1=小模型+后处理，AREA）
  2. 密集人群（flow1，AREA）
- 小模型 `av_algorithm`：3 条（YOLO11n COCO80 检测 × yolo_pytorch/onnxruntime/openvino 引擎，id=2/3/4）

## LLM 视觉端点
- `http://120.79.165.22:17044/v1/models` → 唯一模型 `qwen3.8-27b`（llamacpp GGUF ~35.5B，n_ctx 131072）
- capabilities: `["completion","multimodal"]` → **是视觉模型**
- `LLMUtils.infer(prompt, image_bytes)` 已实现 OpenAI 兼容 image_url base64 + text
- `LLMUtils.check_happen(result, words)`：结果含任意逗号分隔关键词 → True
- flow2/flow3 已能在管线里调 LLM；qwen 走 OpenAI 兼容格式 = 零适配

## 后处理类型（现有 6 种）
AREA/LINE_CROSS/LINE_COUNT/DIRECTION/DENSITY/DWELL
分发位置：
- models.py POST_CHOICES
- biz_rules.py 常量 + SMALL_FLOW_POSTS + LLM_FLOW_POSTS(=(AREA,))
- biz_rules.matched_rules_for_track（统一 dispatch）
- pipeline._update_detector_policy `_force_detect` 白名单（line 135）
- AlgorithmView.valid_posts + UI JSON
- algorithm/index.html 下拉 + help 弹窗；control/index.html isRegionPost/isLinePost；alarm/index.html 事件类型

## DWELL/滞留 调度细节
- `_track_enter_ts[(tid,zid)] = now` 在 `_fire_area_alarms` 里当有匹配规则时记录
- 阈值 = `zone.loiter_threshold`，到达后 `dwell_rules`(AREA/DWELL) 每个算法独立触发一次（`_loiter_fired` 去重）
- DWELL 事件类型 = `dwell`；AREA 超时 = `loiter`

## flow2（纯大模型）触发条件
- `_process_frame`：`if has_motion: self._check_llm_zones(frame, motion_boxes)`
- `llm_rules_for_zone`：flow==2 且 post==AREA 且有 llm+prompt
- 运动盒中心进区域 → LLM 全帧 → 命中 validate → `entered_zone` 报警；8s/区冷却
→ 烟火检测：只要布区域 + 运动触发，符合预期（火焰/烟雾有运动特征）

## flow3（小+大模型）触发条件
- `_flow3_needs_llm(zone_cfg, tr, post)`：匹配当前目标的 flow3 规则
- `_llm_verify_track`：裁剪目标框 → LLM 复核 → 通过才报警；6s/track 冷却
→ 抽烟检测：person 进区域 → AREA 进入报警时 LLM 裁剪人框复核"是否抽烟"→ 命中才报

## REMOVAL（移走检测）设计
- 语义：受保护目标在区域内持续存在 ≥ 阈值，随后离开或消失 → 报警"移走"
- 复用 `_track_enter_ts` 记录"放置时间"，阈值复用 zone.loiter_threshold（0→3s 兜底）
- 触发点 1：track 离开区域（`prev - physical_in` 分支）→ 若该区有 REMOVAL 规则匹配该 track 且停留达标 → 报警
- 触发点 2：track 被 tracker 判定结束（`_last_zone_state` 清理块，目标"凭空消失"）→ 同上报警
- 需要新增 `_last_track_info[tid]` 保存最近一次 track 信息（label/box/algorithm_id），供 track 结束分支用
- 必须加进 `_force_detect` 白名单，否则无运动时不检测（静止物品会被运动门控漏掉）
- REMOVAL 无重复报警问题（一次离开触发一次）；但 track 结束清理时也要 pop `_last_track_info` 防泄漏

## 部署
- 服务器 120.79.165.22，代码 /opt/ai_ma，Docker 容器跑，DB /opt/ai_ma/ai_ma.sqlite3
- apps.py 启动挂 schema_upgrade → 种子代码放这里本地/服务器都生效
- 同步方式待确认（rsync vs docker cp，先看容器名和挂载）

## 校准（2026-09-15 第三批之后）— validate 安全 token 契约 ⚠️ 铁律
- `LLMUtils.check_happen` = 逗号子串匹配 → **裸名词关键词必被否定式假阳性**：
  未吸烟⊃吸烟、未摔倒⊃摔倒、没有灭火器⊃有灭火器（没有=没+有）、未戴手套⊃手套 …（已验证）
- 全部 LLM 算法 validate 改为"否定式不含"的正面 token：
  - PPE 人框复核：`已戴/已穿/已系/已挂/已扣`（对应负面契约 未X）
  - 语义/物体类：`有X` 或专用词（在吸烟/驶离/入梯/移走/堆放/占用/离岗/斗殴/砸物/打电话/奔跑/攀高/倒地/睡觉/有火/有烟），
    负面一律强制模型回复「正常」（正常 不含任何正面 token）
- prompt 统一尾部契约："若……只回复：X。否则只回复：正常/未X。"（qwen 高度遵循）
- `scripts/calibrate_llm_algorithms.py` = 合成正/负帧逐条实测工具（PIL 画帧 + 17044 同管线请求形态）
  - `--selfcheck` 断言防回归（含"没有灭火器⊃有灭火器"已知坑样本）
  - `--name a,b` 多选过滤；`--image f.jpg` 用真实帧替换合成正帧=现场校准入口
- 合成帧实测结论（32 条 LLM 算法）：**27 PASS / 5 待现场真帧**
  - 27 通过：抽烟/烟火/安全帽/安全带/安全钩/反光衣/手套/厨师服/厨师帽/戴口罩/摔倒/攀高/睡岗/
    砸东西/车辆离开/电动车识别/电动车入梯/非绿牌占用/垃圾堆放/垃圾桶/灭火器/锥形桶/危险标签/
    离岗/室内烟火/室内白烟火焰/打架
  - 5 待真帧（合成画质或模型侧不确定）：**奔跑**（正负双向乱判，纯人也判奔跑→部署高风险）、
    **安全帽扣**（帽=头饰/带=领带，画不出）、**绝缘鞋**（黑脚≠鞋）、**物品移走**（负帧误报）、
    **打电话**（无手机的人也判打电话）
  - 现场校准命令示例：`python3 scripts/calibrate_llm_algorithms.py --image 现场截图.jpg --name 奔跑检测`
- 合成帧教训：火柴人画质上限 = 黄色矩形≠反光背心、宽跨步≠奔跑、圆角矩形+轮≠车（补车顶/风挡/大轮后通过）、
  灰圆≠烟（补烟柱火苗后通过）——画不出特征的场景不要用合成帧下结论

## 校准后种子一致性
- seed 脚本升级为"存在即同步"：`[insert]` 缺失插入 / `[update]` prompt/validate 差异原地更新（幂等）
- 校准后三库（本地/容器/服务器）av_biz_algorithm 均 49 条，32 条 LLM prompt/validate 一致
- commit 072a7d5（校准工具+32 条 prompt 调优）已推送
