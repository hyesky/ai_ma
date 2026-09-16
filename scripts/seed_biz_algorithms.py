#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai_ma 业务算法种子脚本（只写数据，不改代码）——按原设计以记录方式新增自定义算法。

用法:
    python3 scripts/seed_biz_algorithms.py [DB路径]
默认 DB 路径: ./ai_ma.sqlite3

幂等：按 name 匹配，已存在则跳过；重复运行安全。
现有能力复用：6 种后处理(AREA/LINE_CROSS/LINE_COUNT/DIRECTION/DENSITY/DWELL)
             + 小模型(id=2 YOLO11n COCO-80) + 大模型(id=1 qwen3.8-27b @120.79.165.22:17044)。

用途划分（与用户清单一一对应）：
- flow1(小模型+后处理)：目标在 COCO-80 且语义可用规则表达 -> DWELL/LINE_COUNT/DENSITY/DIRECTION/AREA/LINE_CROSS
- flow2(大模型全帧判断)：目标不在 COCO-80 或需整体语义（电动车/灭火器/垃圾/离岗/标签/室内烟火等）
- flow3(小模型检出人->大模型复核属性/动作)：PPE 穿戴(帽/扣/口罩/反光衣/手套/绝缘鞋/厨师服帽/安全带钩)及人的动作(奔跑/打电话/摔倒/睡岗/攀高/砸东西)
"""
import os
import sqlite3
import sys
from datetime import datetime

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "ai_ma.sqlite3")

# 字段: name, flow_type(1小+后处理/2大模型/3小+大模型), post_process, small_model_id, target_labels, llm_id, llm_prompt, llm_validate
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
    # —— 大模型视觉复核类（flow3：YOLO 检出人 -> qwen 判断是否吸烟）——
    dict(name="抽烟检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断该人是否正在吸烟。"
                     "吸烟特征：嘴部叼有香烟/烟卷、面部附近有烟雾、手部有吸烟或弹烟灰动作。"
                     "若确定正在吸烟，只回复：吸烟。若没有吸烟或无法判断，只回复：未吸烟。"),
         llm_validate="吸烟"),
    # —— 纯大模型语义类（flow2）——
    dict(name="烟火检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是工业视频监控分析专家。请判断画面中是否出现火焰或烟雾。"
                     "火焰特征：明火、火光、燃烧。烟雾特征：灰白或黑色烟柱、浓烟、起火产生的烟雾。"
                     "若出现火焰，只回复：有火。若出现烟雾但未见明火，只回复：有烟。若两者都有，回复：有烟火。"
                     "若画面正常，只回复：正常。"),
         llm_validate="有火,火情,有烟,浓烟,烟火,冒烟"),
    dict(name="物品移走检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是重点区域防护监控分析专家。该区域内的重要物品（设备、货物、工具等）通常固定摆放。"
                     "请判断画面中是否有重要物品被移走、搬离或丢失（原本摆放物品的位置出现空缺、或画面显示物品正在被搬离）。"
                     "若发现物品被移走或缺失，只回复：移走。若画面正常没有异常，只回复：正常。"),
         llm_validate="移走,被移,搬走,搬离,丢失,不见,空缺"),

    # ================= 第二批（用户新增清单，去重后 40 条） =================
    # ===== A. 滞留类 DWELL（flow1，目标在 COCO-80） =====
    dict(name="车辆违停", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="消防通道占用", flow_type=1, post_process="DWELL", small_model_id=2,
         target_labels=["person", "car", "truck", "bus"], llm_id=None, llm_prompt="", llm_validate=""),
    # ===== B. 计数类 LINE_COUNT（flow1，越线计数） =====
    dict(name="客流统计", flow_type=1, post_process="LINE_COUNT", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="动态人流统计", flow_type=1, post_process="LINE_COUNT", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="动态车流统计", flow_type=1, post_process="LINE_COUNT", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle", "bicycle"], llm_id=None, llm_prompt="", llm_validate=""),
    # ===== C. 密度类 DENSITY（flow1，区域密度超限） =====
    dict(name="区域人流过密", flow_type=1, post_process="DENSITY", small_model_id=2,
         target_labels=["person"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="区域车流过密", flow_type=1, post_process="DENSITY", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆拥堵", flow_type=1, post_process="DENSITY", small_model_id=2,
         target_labels=["car", "truck", "bus"], llm_id=None, llm_prompt="", llm_validate=""),
    # ===== D. 方向/越界/入侵（flow1） =====
    dict(name="车辆逆行", flow_type=1, post_process="DIRECTION", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆越界", flow_type=1, post_process="LINE_CROSS", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    dict(name="车辆入侵", flow_type=1, post_process="AREA", small_model_id=2,
         target_labels=["car", "truck", "bus", "motorcycle"], llm_id=None, llm_prompt="", llm_validate=""),
    # ===== E. 人物属性/穿戴/动作复核（flow3：YOLO 检出 person -> qwen 判断） =====
    dict(name="安全帽检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否佩戴安全帽。"
                     "若佩戴只回复：已戴。若未戴或无法判断只回复：未戴。"),
         llm_validate="已戴,佩戴"),
    dict(name="安全帽扣检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个佩戴安全帽的人，请判断安全帽下颚带（帽扣）是否系好。"
                     "若已系好只回复：已扣。若未系或无法判断只回复：未扣。"),
         llm_validate="已扣,扣好,系好"),
    dict(name="安全带检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人（可能在车内或高处作业），请判断此人是否系好安全带。"
                     "若已系好只回复：已系。若未系或无法判断只回复：未系。"),
         llm_validate="已系,系好"),
    dict(name="安全钩检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人在高处作业，请判断此人身上安全钩/安全绳是否已挂接牢固。"
                     "若已挂接只回复：已挂。若未挂接或无法判断只回复：未挂。"),
         llm_validate="已挂,挂接"),
    dict(name="反光衣检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否穿着反光衣/反光背心（高亮反光条）。"
                     "若穿着只回复：已穿。若未穿或无法判断只回复：未穿。"),
         llm_validate="已穿,穿着,反光"),
    dict(name="绝缘鞋检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人脚上是否穿着绝缘鞋/安全劳保鞋（厚底）。"
                     "若穿着只回复：已穿。若未穿或无法判断只回复：未穿。"),
         llm_validate="已穿,穿着"),
    dict(name="手套检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人双手是否佩戴手套。"
                     "若佩戴只回复：已戴。若未戴或无法判断只回复：未戴。"),
         llm_validate="已戴,佩戴,手套"),
    dict(name="厨师服检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否穿着厨师服/白色工作服。"
                     "若穿着只回复：已穿。若未穿或无法判断只回复：未穿。"),
         llm_validate="已穿,穿着"),
    dict(name="厨师帽检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否佩戴厨师帽/工作帽。"
                     "若佩戴只回复：已戴。若未戴或无法判断只回复：未戴。"),
         llm_validate="已戴,佩戴"),
    dict(name="戴口罩检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否佩戴口罩（遮住口鼻）。"
                     "若佩戴只回复：已戴。若未戴或无法判断只回复：未戴。"),
         llm_validate="已戴,佩戴口罩"),
    dict(name="打电话检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否正在手持手机打电话（手机贴耳）。"
                     "若在打电话只回复：打电话。否则只回复：正常。"),
         llm_validate="打电话,手机通话,手机贴耳"),
    dict(name="奔跑检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否正在奔跑或快速跑动。"
                     "若在奔跑只回复：奔跑。否则只回复：正常。"),
         llm_validate="奔跑,跑步,快跑"),
    dict(name="摔倒检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否摔倒、倒地或躺在地上。"
                     "若是只回复：摔倒。否则只回复：正常。"),
         llm_validate="摔倒,倒地,躺地,跌倒"),
    dict(name="攀高检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否攀爬到高处、或站在货架/平台等高处。"
                     "若在攀高或处于高处只回复：攀高。否则只回复：正常。"),
         llm_validate="攀高,攀爬,爬上,高处"),
    dict(name="睡岗检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是值班岗位监控分析专家。画面中红色框标出一个人，请判断此人是否在睡觉、趴桌打盹或闭眼瞌睡。"
                     "若是只回复：睡觉。否则只回复：正常。"),
         llm_validate="睡觉,瞌睡,打盹,趴睡,睡着"),
    dict(name="砸东西检测", flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。画面中红色框标出一个人，请判断此人是否正在砸、摔或破坏物品。"
                     "若是只回复：砸物。否则只回复：正常。"),
         llm_validate="砸,摔物,破坏,打砸"),
    # ===== F. 整帧语义（flow2：qwen 全帧判断，无小模型） =====
    dict(name="车辆离开", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是重点区域监控分析专家。请判断画面中是否有车辆正在离开/驶离该区域（车头朝外驶出、"
                     "或区域内车辆较常规明显减少）。若是只回复：离开。否则只回复：正常。"),
         llm_validate="离开,驶离,驶出"),
    dict(name="电动车识别", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否出现电动自行车/电动车/电瓶车。"
                     "若是只回复：有电动车。否则只回复：正常。"),
         llm_validate="电动车,电瓶车,电动自行车"),
    dict(name="电动车入电梯检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否有人推电动自行车/电动车进入电梯或楼道。"
                     "若是只回复：入梯。否则只回复：正常。"),
         llm_validate="入梯,电动车,电瓶车,进电梯"),
    dict(name="非绿牌车辆占用", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是停车场监控分析专家。该区域为新能源/专用车位。请判断画面中是否有车辆占用该车位，"
                     "且该车未悬挂绿色新能源车牌（蓝牌/黄牌/无牌）。若是只回复：占用。"
                     "若车位空闲或车辆为绿牌，只回复：正常。"),
         llm_validate="占用,蓝牌,黄牌,无牌"),
    dict(name="垃圾堆放检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是园区监控分析专家。请判断画面中是否堆放有垃圾、建筑废料或杂物堆积。"
                     "若是只回复：堆放。否则只回复：正常。"),
         llm_validate="堆放,垃圾,废料,杂物"),
    dict(name="垃圾桶检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否出现垃圾桶或垃圾箱。"
                     "若是只回复：有垃圾桶。否则只回复：正常。"),
         llm_validate="垃圾桶,垃圾箱"),
    dict(name="灭火器检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是消防监控分析专家。请判断画面中是否出现灭火器（消防器材，通常为红色瓶体）。"
                     "若是只回复：有灭火器。否则只回复：正常。"),
         llm_validate="灭火器"),
    dict(name="锥形桶检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是道路监控分析专家。请判断画面中是否出现交通锥形桶/路锥。"
                     "若是只回复：有锥桶。否则只回复：正常。"),
         llm_validate="锥桶,锥形,路锥,雪糕筒"),
    dict(name="危险货物标签识别", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是化工园区监控分析专家。请判断画面中是否出现危险货物警示标签（易燃/易爆/剧毒/腐蚀/危险品标识等）。"
                     "若是只回复：有危险标签。否则只回复：正常。"),
         llm_validate="危险,易燃,易爆,剧毒,腐蚀,警示"),
    dict(name="离岗检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是值班岗位监控分析专家。该区域应为有人员值守的岗位。请判断画面中是否没有人值守。"
                     "若岗位无人只回复：离岗。若有人在岗只回复：在岗。"),
         llm_validate="离岗,无人,缺岗"),
    dict(name="室内烟火检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是室内安防分析专家。请判断画面中是否出现火焰或烟雾（火灾迹象）。"
                     "若出现火焰只回复：有火。若只有烟雾只回复：有烟。若画面正常只回复：正常。"),
         llm_validate="有火,有烟,烟火,冒烟,浓烟"),
    dict(name="室内白烟火焰检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是室内安防分析专家。请判断画面中是否出现白烟、浓烟或明火火焰。"
                     "若出现火焰只回复：有火。若只有烟雾只回复：有烟。若两者都有回复：有烟火。"
                     "若画面正常只回复：正常。"),
         llm_validate="有火,有烟,烟火,白烟,浓烟"),
    dict(name="打架检测", flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
         llm_id=1,
         llm_prompt=("你是视频监控分析专家。请判断画面中是否存在两人及以上互相扭打、殴打的打架斗殴行为。"
                     "若存在只回复：打架。否则只回复：正常。"),
         llm_validate="打架,斗殴,扭打,殴打"),
]


def main():
    db = os.path.abspath(os.path.expanduser(DB))
    if not os.path.exists(db):
        sys.exit(f"DB 不存在: {db}")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    inserted = 0
    for a in ALGORITHMS:
        if cur.execute("SELECT id FROM av_biz_algorithm WHERE name=?", (a["name"],)).fetchone():
            print(f"[skip] 已存在: {a['name']}")
            continue
        target_labels = a["target_labels"]
        targets_json = "[\"" + "\",\"".join(target_labels) + "\"]" if target_labels else "[]"
        cur.execute(
            "INSERT INTO av_biz_algorithm (name, flow_type, target_labels, llm_prompt, llm_validate,"
            " post_process, state, create_time, last_update_time, llm_id, small_model_id,"
            " ref_angle, angle_tolerance, forward_count_threshold, reverse_count_threshold, detector_model_id)"
            " VALUES (?,?,?,?,?,?,1,?,?,?,?,90.0,45.0,0,0,NULL)",
            (a["name"], a["flow_type"], targets_json, a["llm_prompt"], a["llm_validate"],
             a["post_process"], now, now, a["llm_id"], a["small_model_id"]),
        )
        inserted += 1
        print(f"[insert] {a['name']}  flow={a['flow_type']} post={a['post_process']} "
              f"small={a['small_model_id']} llm={a['llm_id']} targets={target_labels}")
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM av_biz_algorithm").fetchone()[0]
    print(f"\n完成：新增 {inserted} 条，av_biz_algorithm 现有 {total} 条")
    conn.close()


if __name__ == "__main__":
    main()
