#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai_ma 业务算法种子脚本（只写数据，不改代码）——按原设计以记录方式新增自定义算法。

用法:
    python3 scripts/seed_biz_algorithms.py [DB路径]
默认 DB 路径: ./ai_ma.sqlite3

幂等：按 name 匹配，已存在则跳过；重复运行安全。
新增算法全部复用现有 6 种后处理 + 现有小模型(id=2 YOLO11n) + 现有大模型(id=1 qwen/qwen3-vl-8b @120.79.165.22:17044)。
"""
import os
import sqlite3
import sys
from datetime import datetime

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "ai_ma.sqlite3")

# 字段: name, flow_type(1小模型+后处理/2纯大模型/3小+大模型), post_process, small_model_id, target_labels, llm_id, llm_prompt, llm_validate
ALGORITHMS = [
    # —— 滞留类（DWELL）：徘徊 / 遗留 / 违法停车 / 通道占用，纯小模型即可 ——
    dict(
        name="人员徘徊检测",
        flow_type=1, post_process="DWELL", small_model_id=2, target_labels=["person"],
        llm_id=None, llm_prompt="", llm_validate="",
    ),
    dict(
        name="遗留物品检测",
        flow_type=1, post_process="DWELL", small_model_id=2,
        target_labels=["suitcase", "backpack", "handbag"],
        llm_id=None, llm_prompt="", llm_validate="",
    ),
    dict(
        name="违法停车检测",
        flow_type=1, post_process="DWELL", small_model_id=2,
        target_labels=["car", "truck", "bus", "motorcycle"],
        llm_id=None, llm_prompt="", llm_validate="",
    ),
    dict(
        name="通道占用检测",
        flow_type=1, post_process="DWELL", small_model_id=2,
        target_labels=["person", "car", "truck", "bus"],
        llm_id=None, llm_prompt="", llm_validate="",
    ),
    # —— 大模型视觉语义类（flow 2/3）——
    dict(
        name="抽烟检测",
        flow_type=3, post_process="AREA", small_model_id=2, target_labels=["person"],
        llm_id=1,
        llm_prompt=(
            "你是视频监控分析专家。画面中红色框标出一个人，请判断该人是否正在吸烟。"
            "吸烟特征：嘴部叼有香烟/烟卷、面部附近有烟雾、手部有吸烟或弹烟灰动作。"
            "若确定正在吸烟，只回复：吸烟。若没有吸烟或无法判断，只回复：未吸烟。"
        ),
        llm_validate="吸烟",
    ),
    dict(
        name="烟火检测",
        flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
        llm_id=1,
        llm_prompt=(
            "你是工业视频监控分析专家。请判断画面中是否出现火焰或烟雾。"
            "火焰特征：明火、火光、燃烧。烟雾特征：灰白或黑色烟柱、浓烟、起火产生的烟雾。"
            "若出现火焰，只回复：有火。若出现烟雾但未见明火，只回复：有烟。若两者都有，回复：有烟火。"
            "若画面正常，只回复：正常。"
        ),
        llm_validate="有火,火情,有烟,浓烟,烟火,冒烟",
    ),
    dict(
        name="物品移走检测",
        flow_type=2, post_process="AREA", small_model_id=None, target_labels=[],
        llm_id=1,
        llm_prompt=(
            "你是重点区域防护监控分析专家。该区域内的重要物品（设备、货物、工具等）通常固定摆放。"
            "请判断画面中是否有重要物品被移走、搬离或丢失（原本摆放物品的位置出现空缺、或画面显示物品正在被搬离）。"
            "若发现物品被移走或缺失，只回复：移走。若画面正常没有异常，只回复：正常。"
        ),
        llm_validate="移走,被移,搬走,搬离,丢失,不见,空缺",
    ),
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
