# Ai_ma

多路视频接入与智能布控分析平台。支持 GB28181 / RTSP、YOLO 小模型检测、OpenAI 兼容大模型复核、多边形布控与结构化报警。

| 链接 | |
|------|--|
| 作者 | ai_ma |

**开源协议：** MIT License，可自由商用。详见 `LICENSE`。

---

## 功能

- 视频接入：RTSP / GB28181 拉流，ZLMediaKit 转发，ONVIF 发现
- 智能分析：YOLO-PyTorch / ONNX / OpenVINO 小模型 + 可选大模型复核
- 布控报警：多边形区域、6 种后处理规则（入侵 / 越线 / 计数 / 密度 / 方向 / 滞留）
- 算法库：内置 49 个业务算法（通用安防 / 行为交通 / PPE 穿戴 / 大模型语义），详见「业务算法库」
- 运维：控制面板监控、流媒体启停、录像、多语言（7 种）

---

## 业务算法库（内置 49 个）

业务算法 = `av_biz_algorithm` 数据记录，命中规则即报警。分三类识别流程：

| 流程 | 含义 | 检测方式 |
|------|------|----------|
| flow1 小模型+后处理 | YOLO 检出目标 → 几何后处理 | 区域(AREA)/滞留(DWELL)/越线(LINE_CROSS)/计数(LINE_COUNT)/密度(DENSITY)/方向(DIRECTION) |
| flow2 大模型+后处理 | 运动触发 → 大模型全帧语义判断 | 大模型（qwen 视觉）全帧理解后 `validate` 关键词命中才报警 |
| flow3 小模型+大模型复核 | YOLO 检出 person → 裁剪人框 → 大模型复核 | 判定穿戴/行为后才报警（防小模型误报） |

### 通用安防（flow1，6 个）

| 算法 | 目标类别 |
|------|----------|
| 人员区域入侵 | person |
| 密集人群 | person |
| 人员徘徊检测 | person |
| 遗留物品检测 | suitcase / backpack / handbag |
| 违法停车检测 | car / truck / bus / motorcycle |
| 通道占用检测 | person / car / truck / bus |

### 行为与交通（flow1，11 个）

| 算法 | 后处理 |
|------|--------|
| 车辆违停 | DWELL |
| 消防通道占用 | DWELL |
| 客流统计 | LINE_COUNT |
| 动态人流统计 | LINE_COUNT |
| 动态车流统计 | LINE_COUNT |
| 区域人流过密 | DENSITY |
| 区域车流过密 | DENSITY |
| 车辆拥堵 | DENSITY |
| 车辆逆行 | DIRECTION |
| 车辆越界 | LINE_CROSS |
| 车辆入侵 | AREA |

### PPE 穿戴与人员行为（flow3，17 个）

安全帽检测、安全帽扣检测、安全带检测、安全钩检测、反光衣检测、绝缘鞋检测、手套检测、厨师服检测、厨师帽检测、戴口罩检测、打电话检测、奔跑检测、摔倒检测、攀高检测、睡岗检测、砸东西检测、抽烟检测

> 均为 YOLO 检出 person → 裁剪人框 → 大模型复核：「已戴 / 已穿 / 已系 / 已挂 / 已扣」等正面契约词命中才报警，负面回复（未X）不误报。

### 大模型语义识别（flow2，15 个）

烟火检测、物品移走检测、车辆离开、电动车识别、电动车入电梯检测、非绿牌车辆占用、垃圾堆放检测、垃圾桶检测、灭火器检测、锥形桶检测、危险货物标签识别、离岗检测、室内烟火检测、室内白烟火焰检测、打架检测

> flow2/flow3 的 prompt 已按「validate 安全 token 契约」调优：判定是子串匹配，负面回复统一契约「正常 / 未X」，正面只放不会出现在否定句里的关键词（如「有灭火器」而非「灭火器」），系统性防假阳性。`scripts/calibrate_llm_algorithms.py` 可对每条大模型算法做合成帧 / 现场真帧校准（`--selfcheck` / `--name` / `--image`）。

---

## 扩展新算法（记录即算法，零代码）

新增业务算法**不需要改任何代码**——所有算法都是数据记录，前端「业务算法」页可直接增删改，或运行种子脚本批量同步。

选择流程：

1. COCO-80 能检出 → **flow1** + 几何后处理（AREA / DWELL / LINE_COUNT / DENSITY / DIRECTION / LINE_CROSS）
2. 非 COCO 或整体语义 → **flow2** + AREA（大模型全帧判断）
3. PPE 穿戴 / 人的动作 → **flow3** + AREA（YOLO 人框 + 大模型复核）

```bash
# 批量同步（幂等：已存在则更新 prompt/validate，缺失才插入）
python3 scripts/seed_biz_algorithms.py            # 默认 ./ai_ma.sqlite3
python3 scripts/seed_biz_algorithms.py /path/to/ai_ma.sqlite3

# 大模型算法实测校准（合成正/负帧走管线同款请求调 LLM）
python3 scripts/calibrate_llm_algorithms.py --selfcheck
python3 scripts/calibrate_llm_algorithms.py --name 打架检测
python3 scripts/calibrate_llm_algorithms.py --image 现场截图.jpg --name 奔跑检测
```

---

## 环境要求

- Python 3.10+
- FFmpeg（PATH 或 `config.json` 配置）
- ZLMediaKit（流媒体，端口与 `config.json` 一致）
- GPU 可选


```bash
如果是Linux系统，需要手动进入到zlm/bin.x86.gcc9.4 或 zlm/bin.arm.gcc9.4 ，确保可以正确执行 ./ai_ma_zlm


如果执行./ai_ma_zlm失败了，可以参考下面的两种方式解决安装环境问题

（1）解决方式一
sudo chmod -R a+x *
echo "export LD_LIBRARY_PATH=\"$(pwd):$LD_LIBRARY_PATH\"" >> ~/.bashrc && source ~/.bashrc

（2）解决方式二

sudo apt update
sudo apt install -y libsrtp2-1

//下载ubuntu20的libssl1.1包
wget http://security.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb
sudo dpkg -i libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb

//修复依赖
sudo apt -f install

```

**安装依赖：**

```bash
# Windows
pip install -r requirements-windows.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
或
pip install -r requirements-windows.txt

# Linux
pip install -r requirements-linux.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
或
pip install -r requirements-linux.txt
```

---

## 快速开始

```bash
python manage.py runserver 0.0.0.0:10001
```

浏览器访问 `http://<host>:10001/`，默认账号 `admin`，默认密码 `admin888`。

首次部署请编辑 `config.json`（端口、ZLM、FFmpeg 等）和 `settings.json`（界面品牌）。启动配置页保存后多数项热更新生效；改管理端口或调试日志需重启服务。

---

## 使用顺序

```
视频管理 → 小模型 → 大模型 → 业务算法 → 布控管理 → 启动分析 → 报警管理
```

1. 添加摄像头并确认拉流正常
2. 上传/配置小模型（流程 1/3）和大模型（流程 2/3）
3. 创建业务算法，在布控页画区域并绑定算法
4. 点击「启动分析」（**重启服务后需手动再点**）
5. 在报警管理查看结果

> 只有业务算法规则命中才会报警；单纯检测到目标或画面运动不会产生报警记录。

---

## 常见问题

| 问题 | 处理 |
|------|------|
| 没有报警 | 确认拉流正常、布控已绑算法、已启动分析、检测类别匹配 |
| 改配置不生效 | 布控/算法可热更新；换小模型需重启分析；改端口需重启服务 |
| 大模型算法不报警 | 确认已配大模型（流程 2/3 必选）、布控区域触发运动；可用校准脚本实测该算法 |
| 端口占用 | 结束残留 `python.exe` 后重新启动 |

日志目录：`log/`。版本号见 `framework/settings.py`。

---

## 更新日志

### 2026-09-16（算法库扩充与校准）
- **内置业务算法扩充至 49 个**（原 9 个 → 49 个）：新增通用安防延展、行为与交通统计、PPE 穿戴复核、大模型语义识别四大类（见「业务算法库」），均为数据记录，零代码改动
- **32 个大模型算法 prompt 调优**（validate 安全 token 契约）：修复 `未吸烟⊃吸烟`、`没有灭火器⊃有灭火器` 等否定式子串误报问题；负面回复统一契约「正常 / 未X」
- **新增校准工具** `scripts/calibrate_llm_algorithms.py`：合成正/负帧逐条实测大模型算法（PASS/FAIL），支持现场真帧校准（`--image`）
- 47 条算法入库记录可经 `scripts/seed_biz_algorithms.py` 幂等同步到任意环境

### v1.003
- **业务算法选择大模型相关修复（重要）**
  - 大模型配置新增「名称」字段，可留空；新增 / 编辑时若名称为空，自动以「模型名称」兜底（`name = model_name`），避免大模型配置出现空名称。
  - 业务算法列表 / 编辑中，绑定大模型的显示名现在会回退到「模型名称」（`llm_name` 兜底 `name or model_name`），不再显示空白。
  - **修复业务算法编辑时，绑定的大模型若已被禁用，下拉框无法回显、看似「配置丢失 / 选不中」的问题**：现在自动补一个带「[禁用]」标记的回显项，且每次打开编辑会清理上一次的回显项。
  - 业务算法「大模型」下拉选项 label 改为 `name || model_name || #id`，确保只填了模型名称时也能正确显示。
- **新增「统计看板」（报警态势总览）**
  - 报警管理新增「统计看板」页面（`/alarm/dashboard`），一站式掌握报警态势。
  - 4 张核心统计卡：今日报警、近 7 天报警、累计报警、涉及摄像头数（均可点击下钻到对应列表）。
  - 报警趋势图：支持近 7 天 / 近 30 天切换。
  - 报警类型分布、报警 TOP 摄像头排行。
  - 新增接口 `alarm/openStats`，左侧导航新增「统计看板」入口。
- **国际化补全**
  - 补齐统计看板相关 16 个翻译键至全部 7 种语言（es / ko / ru / vi / zh-hk / zh / en），修复此前仅 zh / en 有译、其余语言界面显示原始 key 的问题。

> 版本号见 `framework/settings.py` 的 `PROJECT_VERSION`。
