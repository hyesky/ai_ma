#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai_ma 业务算法种子脚本（只写数据，不改代码）——按原设计以记录方式新增/校准自定义算法。

用法:
    python3 scripts/seed_biz_algorithms.py [DB路径]
默认 DB 路径: ./ai_ma.sqlite3

幂等 + 同步：按 name 匹配；不存在则 INSERT，已存在但 prompt/validate 不同则 UPDATE（三库一致用）。

⚠️ validate 关键词铁律：必须用"否定式不包含"的安全 token。
   check_happen 是逗号子串匹配，裸名词（如 吸烟/打架/摔倒/灭火器）会被「未吸烟/未打架/未摔倒/没有灭火器」
   误命中 → 假阳性。安全写法：PPE 用「已戴/已穿/已系/已挂/已扣」，语义类让模型正面回「有X/专用词」、
   负面一律强制「正常」，validate 只放正面 token。

现有能力复用：6 种后处理(AREA/LINE_CROSS/LINE_COUNT/DIRECTION/DENSITY/DWELL)
             + 小模型(id=2 YOLO11n COCO-80) + 大模型(id=1 qwen3.8-27b @120.79.165.22:17044)。

flow 约定：1=小模型+后处理；2=大模型全帧；3=小模型检出人->大模型复核属性/动作。
"""
import os
import sqlite3
import sys
from datetime import datetime

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "ai_ma.sqlite3")

# 字段: name, flow_type(1/2/3), post_process, small_model_id, target_labels, llm_id, llm_prompt, llm_validate
ALGORITHMS = [
    # ================= 第一批（2026-09-15 已交付） =================
    # —— 滞留类（DWELL）：徘徊 / 遗留 / 违法停车 / 通道占用，纯小模型即可 ——
    dict(name="人员徘徊检测", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="遗留物品检测", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["suitcase", "backpack", "handbag"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="违法停车检测", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="通道占用检测", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["person", "car", "truck", "bus"], llm_id=None, llm_prompt="", llm_validate=""),
    # —— flow3：YOLO 检出人 -> qwen 判断是否吸烟（validate 用「在吸烟」，避开「未吸烟」子串污染）——
    dict(name="抽烟检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断该人是否正在吸烟。"
                     "吸烟特征：嘴部叼有香烟、面部附近有烟雾、手部有点烟或吸烟动作。"
                     "若确定正在吸烟，只回复：在吸烟。若没有吸烟或无法判断，只回复：正常。"),
         llm_validate="在吸烟"),
    # —— flow2：纯大模型整帧 ——
    dict(name="烟火检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是工业视频监控分析专家。请判断画面中是否出现火焰或烟雾。"
                     "若出现明火，只回复：有火。若只见烟雾未见明火，只回复：有烟。若两者都有，回复：有火。"
                     "若画面正常，只回复：正常。"),
         llm_validate="有火,有烟"),
    dict(name="物品移走检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是重点区域防护监控分析专家。该区域内的重要物品（设备、货物、工具等）通常固定摆放。"
                     "请判断画面中是否有重要物品被移走、搬离或丢失（原本摆放位置出现空缺、物品正在被搬离）。"
                     "若发现物品被移走或缺失，只回复：移走。若画面正常，只回复：正常。"),
         llm_validate="移走"),

    # ================= 第二批（用户清单，去重后 40 条） =================
    # ----- A. 滞留 DWELL / 计数 LINE_COUNT / 密度 DENSITY / 方向/越线/区域（flow1） -----
    dict(name="车辆违停", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="消防通道占用", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["person", "car", "truck", "bus"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="客流统计", flow_type=1, post_process="LINE_COUNT", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="动态人流统计", flow_type=1, post_process="LINE_COUNT", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="动态车流统计", flow_type=1, post_process="LINE_COUNT", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle", "bicycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="区域人流过密", flow_type=1, post_process="DENSITY", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="区域车流过密", flow_type=1, post_process="DENSITY", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆拥堵", flow_type=1, post_process="DENSITY", small_model_id=2,
         target_labels=["car", "truck", "bus"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆逆行", flow_type=1, post_process="DIRECTION", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆越界", flow_type=1, post_process="LINE_CROSS", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆入侵", flow_type=1, post_process="AREA", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    # ----- B. flow3：人框复核（validate 一律「已X」前缀，避免 未X ⊃ X 假阳性） -----
    dict(name="安全帽检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否佩戴安全帽。"
                     "若佩戴，只回复：已戴。若未戴或无法判断，只回复：未戴。"),
         llm_validate="已戴"),
    dict(name="安全帽扣检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个戴安全帽的人，请判断安全帽下颚带（帽扣）是否系好。"
                     "若已系好，只回复：已扣。若未系或无法判断，只回复：未扣。"),
         llm_validate="已扣"),
    dict(name="安全带检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人（可能在车内或高处作业），请判断此人是否系好安全带。"
                     "若已系好，只回复：已系。若未系或无法判断，只回复：未系。"),
         llm_validate="已系"),
    dict(name="安全钩检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人在高处作业，请判断此人身上安全钩/安全绳是否已挂接牢固。"
                     "若已挂接，只回复：已挂。若未挂接或无法判断，只回复：未挂。"),
         llm_validate="已挂"),
    dict(name="反光衣检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否穿着反光衣/反光背心（高亮反光条）。"
                     "若穿着，只回复：已穿。若未穿或无法判断，只回复：未穿。"),
         llm_validate="已穿"),
    dict(name="绝缘鞋检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人脚上是否穿着绝缘鞋/安全劳保鞋（厚底）。"
                     "若穿着，只回复：已穿。若未穿或无法判断，只回复：未穿。"),
         llm_validate="已穿"),
    dict(name="手套检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人双手是否佩戴手套。"
                     "若佩戴，只回复：已戴。若未戴或无法判断，只回复：未戴。"),
         llm_validate="已戴"),
    dict(name="厨师服检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否穿着厨师服/白色工作服。"
                     "若穿着，只回复：已穿。若未穿或无法判断，只回复：未穿。"),
         llm_validate="已穿"),
    dict(name="厨师帽检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否佩戴厨师帽/工作帽。"
                     "若佩戴，只回复：已戴。若未戴或无法判断，只回复：未戴。"),
         llm_validate="已戴"),
    dict(name="戴口罩检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否佩戴口罩（遮住口鼻）。"
                     "若佩戴，只回复：已戴。若未戴或无法判断，只回复：未戴。"),
         llm_validate="已戴"),
    dict(name="打电话检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否手持手机打电话（手机贴耳）。"
                     "若在打电话，只回复：打电话。若没有，只回复：正常。"),
         llm_validate="打电话"),
    dict(name="奔跑检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否正在奔跑或快速跑动。"
                     "若在奔跑，只回复：奔跑。若没有，只回复：正常。"),
         llm_validate="奔跑"),
    dict(name="摔倒检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否倒地、摔倒或躺在地上。"
                     "若倒地，只回复：倒地。若没有，只回复：正常。"),
         llm_validate="倒地"),
    dict(name="攀高检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否攀爬到高处、或站在货架/平台等高处。"
                     "若在攀高或处于高处，只回复：攀高。若没有，只回复：正常。"),
         llm_validate="攀高"),
    dict(name="睡岗检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是值班岗位监控分析专家。画面中红色框标出一个人，请判断此人是否在睡觉、趴桌打盹或闭眼瞌睡。"
                     "若在睡觉，只回复：睡觉。若没有，只回复：正常。"),
         llm_validate="睡觉"),
    dict(name="砸东西检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否正在砸、摔或破坏物品。"
                     "若在砸物，只回复：砸物。若没有，只回复：正常。"),
         llm_validate="砸物"),
    # ----- C. flow2：整帧语义（validate 用「有X」前缀或专用词，负面强制「正常」，避开 没有X ⊃ X） -----
    dict(name="车辆离开", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是重点区域监控分析专家。请判断画面中是否有车辆正在离开/驶离该区域（车头朝外驶出、"
                     "或区域内车辆明显减少）。若是，只回复：驶离。若不是，只回复：正常。"),
         llm_validate="驶离"),
    dict(name="电动车识别", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否出现电动自行车/电动车/电瓶车。"
                     "若是，只回复：有电动车。若不是，只回复：正常。"),
         llm_validate="有电动车"),
    dict(name="电动车入电梯检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否有人推电动自行车/电动车进入电梯或楼道。"
                     "若是，只回复：入梯。若不是，只回复：正常。"),
         llm_validate="入梯"),
    dict(name="非绿牌车辆占用", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是停车场监控分析专家。该区域为新能源专用车位。请判断画面中是否有车辆占用该车位，"
                     "且该车未悬挂绿色新能源牌照（蓝牌/黄牌/无牌）。若是，只回复：占用。"
                     "若车位空闲或车辆为绿牌，只回复：正常。"),
         llm_validate="占用"),
    dict(name="垃圾堆放检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是园区监控分析专家。请判断画面中是否堆放有垃圾、建筑废料或杂物堆积。"
                     "若堆放，只回复：堆放。若没有，只回复：正常。"),
         llm_validate="堆放"),
    dict(name="垃圾桶检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否出现垃圾桶或垃圾箱。"
                     "若是，只回复：有垃圾桶。若不是，只回复：正常。"),
         llm_validate="有垃圾桶"),
    dict(name="灭火器检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是消防监控分析专家。请判断画面中是否出现灭火器（消防器材，通常为红色瓶体）。"
                     "若是，只回复：有灭火器。若不是，只回复：正常。"),
         llm_validate="有灭火器"),
    dict(name="锥形桶检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是道路监控分析专家。请判断画面中是否出现交通锥形桶/路锥。"
                     "若是，只回复：有锥桶。若不是，只回复：正常。"),
         llm_validate="有锥桶"),
    dict(name="危险货物标签识别", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是化工园区监控分析专家。请判断画面中是否出现危险货物警示标签（易燃/易爆/剧毒/腐蚀等危险标识）。"
                     "若是，只回复：有危险标签。若不是，只回复：正常。"),
         llm_validate="有危险标签"),
    dict(name="离岗检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是值班岗位监控分析专家。该区域应为有人员值守的岗位。请判断画面中是否没有人值守。"
                     "若岗位无人，只回复：离岗。若有人在岗，只回复：在岗。"),
         llm_validate="离岗"),
    dict(name="室内烟火检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是室内安防分析专家。请判断画面中是否出现火焰或烟雾（火灾迹象）。"
                     "若出现明火，只回复：有火。若只见烟雾未见明火，只回复：有烟。"
                     "若画面正常，只回复：正常。"),
         llm_validate="有火,有烟"),
    dict(name="室内白烟火焰检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是室内安防分析专家。请判断画面中是否出现白烟、浓烟或明火火焰。"
                     "若出现明火，只回复：有火。若只见烟雾未见明火，只回复：有烟。"
                     "若画面正常，只回复：正常。"),
         llm_validate="有火,有烟"),
    dict(name="打架检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否存在两人及以上互相扭打、殴打的打架斗殴行为。"
                     "若发生斗殴，只回复：斗殴。若没有，只回复：正常。"),
         llm_validate="斗殴"),
]


def main():
    db = os.path.abspath(os.path.expanduser(DB))
    if not os.path.exists(db):
        sys.exit(f"DB 不存在: {db}")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    inserted = updated = 0
    for a in ALGORITHMS:
        target_labels = a["target_labels"]
        targets_json = "[\"" + "\",\"".join(target_labels) + "\"]" if target_labels else "[]"
        exists = cur.execute("SELECT id, llm_prompt, llm_validate FROM av_biz_algorithm WHERE name=?",
                             (a["name"],)).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO av_biz_algorithm (name, flow_type, target_labels, llm_prompt, llm_validate,"
                " post_process, state, create_time, last_update_time, llm_id, small_model_id,"
                " ref_angle, angle_tolerance, forward_count_threshold, reverse_count_threshold, detector_model_id)"
                " VALUES (?,?,?,?,?,?,1,?,?,?,?,90.0,45.0,0,0,NULL)",
                (a["name"], a["flow_type"], targets_json, a["llm_prompt"], a["llm_validate"],
                 a["post_process"], now, now, a["llm_id"], a["small_model_id"]),
            )
            inserted += 1
            print(f"[insert] {a['name']}  flow={a['flow_type']} post={a['post_process']}")
            continue
        # 已存在：prompt/validate 有差异则同步（校准用）
        if exists[1] != a["llm_prompt"] or exists[2] != a["llm_validate"]:
            cur.execute(
                "UPDATE av_biz_algorithm SET llm_prompt=?, llm_validate=?, last_update_time=? WHERE id=?",
                (a["llm_prompt"], a["llm_validate"], now, exists[0]),
            )
            updated += 1
            print(f"[update] {a['name']}  prompt/validate 已同步")
        else:
            print(f"[skip ] {a['name']}")
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM av_biz_algorithm").fetchone()[0]
    print(f"\n完成：新增 {inserted}、更新 {updated}；av_biz_algorithm 现有 {total} 条")
    conn.close()


if __name__ == "__main__":
    main()
