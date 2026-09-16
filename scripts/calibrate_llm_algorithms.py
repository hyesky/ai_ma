#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 视觉算法提示词校准——合成正/负帧逐条实测 17044，报告回复是否命中 llm_validate 关键词。

用法:
    python3 scripts/calibrate_llm_algorithms.py                  # 全部 LLM 算法，正+负帧
    python3 scripts/calibrate_llm_algorithms.py --name 安全帽检测
    python3 scripts/calibrate_llm_algorithms.py --image a.jpg --name 打架检测   # 现场帧校准（替换正帧）
    python3 scripts/calibrate_llm_algorithms.py --only-positive --max 5        # 只看正帧、限 5 条
    python3 scripts/calibrate_llm_algorithms.py --selfcheck      # 跑内置断言

合成帧仅用于验证"提示词→回复→关键词"链路；真实精度需现场相机抓帧（--image）。
"""
import argparse
import base64
import io
import os
import sqlite3
import sys
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "..", "ai_ma.sqlite3")

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("缺少 pillow: pip install pillow 后重试")


# ---------------- 绘图基础 ----------------
def new_frame(w=512, h=384):
    im = Image.new("RGB", (w, h), (212, 212, 210))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 260, w, h], fill=(148, 143, 138))  # 地面
    d.rectangle([0, 0, w, 260], fill=(216, 216, 214))  # 墙壁
    d.rectangle([400, 60, 478, 150], outline=(120, 120, 118), width=4)  # 窗户
    return im, d


SKIN = (235, 190, 150)
CLOTH = (58, 58, 92)
HARD = (255, 200, 40)


def draw_person(d, x, g, spec):
    """简化小人。g=脚底 y。spec: stance(stand/run/lie/sit/climb), 及帽子/口罩等附件。"""
    s = spec.get("stance", "stand")
    head = spec.get("head", True)

    def circle(c, r, fill):
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=fill)

    if s == "lie":  # 倒地/躺地
        hin = spec.get("head_x", x - 45)
        circle((hin, g - 18), 20, SKIN)
        d.line([(hin + 8, g - 15), (hin + 70, g - 20)], fill=CLOTH, width=10)
        d.line([(hin + 70, g - 20), (hin + 120, g - 18)], fill=CLOTH, width=8)
        return

    # 站立姿态
    hy = g - 150  # 头顶
    circle((x, hy + 20), 20, SKIN)
    lean = 4 if s == "run" else 0
    d.line([(x, hy + 38), (x + lean, hy + 92)], fill=CLOTH, width=12)  # 躯干
    # 袖子/手臂
    top = hy + 40
    if s == "run":
        d.line([(x - 8, top), (x - 40, top + 8)], fill=CLOTH, width=7)   # 前摆臂
        d.line([(x + 8, top), (x + 36, top + 36)], fill=CLOTH, width=7)  # 后摆臂
        for i in range(3):  # 身后动感线
            d.line([(x - 56 - i * 12, top - 8 + i * 10), (x - 42 - i * 12, top + i * 10)],
                   fill=(130, 130, 130), width=3)
    elif spec.get("phone"):
        d.line([(x + 10, top), (x + 32, top + 6)], fill=CLOTH, width=7)  # 手举到耳
    elif spec.get("smash"):
        d.line([(x - 8, top), (x - 40, top - 30)], fill=CLOTH, width=7)  # 高举砸
        d.line([(x + 8, top), (x + 40, top + 20)], fill=CLOTH, width=7)
    else:
        d.line([(x - 8, top), (x - 34, top + 42)], fill=CLOTH, width=7)
        d.line([(x + 8, top), (x + 34, top + 42)], fill=CLOTH, width=7)
    # 腿
    hip = hy + 90
    if s == "run":
        d.line([(x - 4, hip), (x - 40, g - 2)], fill=CLOTH, width=9)  # 大跨步前腿
        d.line([(x + 4, hip), (x + 44, g)], fill=CLOTH, width=9)      # 蹬直后腿
    elif s == "sit":  # 坐在椅子上（睡岗用）
        d.line([(x - 4, hip), (x - 12, g - 20)], fill=CLOTH, width=9)
        d.line([(x + 4, hip), (x + 16, g - 20)], fill=CLOTH, width=9)
        d.rectangle([x - 26, g - 24, x + 26, g - 6], fill=(90, 70, 50))  # 椅子面
    else:
        d.line([(x - 4, hip), (x - 12, g)], fill=CLOTH, width=9)
        d.line([(x + 4, hip), (x + 16, g)], fill=CLOTH, width=9)

    # ---- 附件 ----
    hc = (x, hy + 20)
    if spec.get("helmet"):  # 安全帽
        d.arc([hc[0] - 22, hc[1] - 28, hc[0] + 22, hc[1] + 4], 180, 360, fill=HARD, width=8)
        d.line([(hc[0] - 20, hc[1] - 8), (hc[0] + 20, hc[1] - 8)], fill=HARD, width=6)
        d.line([(hc[0] - 14, hc[1] - 22), (hc[0], hc[1] - 30)], fill=HARD, width=4)
    elif spec.get("chefhat"):  # 厨师帽
        d.rounded_rectangle([hc[0] - 18, hc[1] - 30, hc[0] + 18, hc[1] - 12], 9, fill=(248, 248, 246))
        d.line([(hc[0], hc[1] - 30), (hc[0], hc[1] - 38)], fill=(248, 248, 246), width=10)
    if spec.get("mask"):  # 口罩（盖下半脸）
        d.rounded_rectangle([hc[0] - 18, hc[1] + 6, hc[0] + 18, hc[1] + 20], 8, fill=(240, 240, 240))
    if spec.get("seatbelt"):  # 安全带斜带
        d.line([(x - 10, hy + 42), (x + 8, hy + 88)], fill=(200, 40, 40), width=6)
    if spec.get("vest"):  # 反光背心（叠在深色上衣外，黄绿+银白反光条）
        d.rectangle([x - 11, hy + 38, x + 11, hy + 74], fill=(210, 230, 60))
        d.rectangle([x - 9, hy + 52, x + 9, hy + 60], fill=(245, 245, 245))
        d.rectangle([x - 9, hy + 62, x + 9, hy + 70], fill=(245, 245, 245))
    if spec.get("uniform"):  # 厨师服（白上衣）
        d.line([(x, hy + 38), (x, hy + 92)], fill=(245, 244, 242), width=14)
    if spec.get("gloves"):  # 手套（白手套）
        circle((x - 34, top + 42), 6, (235, 235, 230))
        circle((x + 34, top + 42), 6, (235, 235, 230))
    if spec.get("boots"):  # 绝缘鞋
        d.rounded_rectangle([x - 22, g - 8, x - 4, g], 3, fill=(30, 30, 30))
        d.rounded_rectangle([x + 2, g - 8, x + 20, g], 3, fill=(30, 30, 30))
    if spec.get("hook"):  # 安全钩+安全绳
        d.line([(x, hy + 40), (x, hy - 10)], fill=(60, 60, 60), width=4)
        circle((x, hy - 10), 7, (200, 200, 200))
    if spec.get("phone"):  # 手机（耳边深色方块）
        d.rectangle([x + 32, hy + 2, x + 46, hy + 18], fill=(40, 40, 40))
    if spec.get("cigarette"):  # 香烟
        d.rectangle([hc[0] + 16, hc[1] + 14, hc[0] + 34, hc[1] + 20], fill=(245, 245, 240))
        d.polygon([(hc[0] + 34, hc[1] + 14), (hc[0] + 42, hc[1] + 10), (hc[0] + 30, hc[1] + 6)], fill=(200, 200, 200))
    if spec.get("sleepy"):  # 闭眼
        d.line([(hc[0] - 10, hc[1] - 2), (hc[0] - 3, hc[1])], fill=(90, 60, 30), width=3)
        d.line([(hc[0] + 3, hc[1]), (hc[0] + 10, hc[1] - 2)], fill=(90, 60, 30), width=3)


def to_png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


# ---------------- 场景目录 ----------------
def room(**spec):
    im, d = new_frame()
    return im


def person(**spec):
    im, d = new_frame()
    draw_person(d, 256, 260, spec)
    return im


def two_people(fight=False):
    im, d = new_frame()
    draw_person(d, 205, 260, dict(stance="run"))
    draw_person(d, 315, 260, dict(stance="run"))
    if fight:
        d.polygon([(256, 190), (270, 165), (284, 190), (270, 180)], fill=(230, 40, 40))
        d.line([(240, 210), (292, 205)], fill=(80, 80, 80), width=6)
    return im


def desk(scene):
    im, d = new_frame()
    d.rectangle([380, 120, 480, 180], fill=(150, 110, 70))  # 办公桌（右）
    if scene == "manned":
        draw_person(d, 256, 260, dict(stance="sit"))
    elif scene == "sleep":
        draw_person(d, 300, 260, dict(stance="sit", sleepy=True))
        d.arc([268, 168, 332, 232], 0, 180, fill=(60, 60, 60), width=6)  # 趴桌上
    return im


def climbing():
    im, d = new_frame()
    d.rectangle([176, 120, 336, 260], fill=(190, 140, 90), outline=(120, 90, 60), width=4)  # 高台
    draw_person(d, 256, 122, dict(stance="stand"))
    return im


def carrying(empty=True):
    im, d = new_frame()
    if empty:  # 物品被搬走：台上空 + 人搬箱走向画面边缘
        d.rectangle([150, 190, 250, 260], fill=(170, 168, 164), outline=(110, 110, 110), width=3)  # 空台
        d.rectangle([160, 120, 216, 170], outline=(90, 90, 90), width=3)  # 原物位置虚线
        d.rectangle([360, 150, 416, 210], fill=(150, 120, 80))  # 被搬的箱
        draw_person(d, 392, 260, dict(stance="run"))
    else:  # 物品在台上
        d.rectangle([150, 180, 250, 260], fill=(170, 168, 164), outline=(110, 110, 110), width=3)
        d.rectangle([172, 140, 228, 190], fill=(150, 120, 80))
    return im


def parking(bay, plate):
    """bay: empty/none; plate: blue/green。非绿牌占用：蓝色牌车占新能源位。"""
    im, d = new_frame()
    d.rectangle([120, 220, 400, 260], outline=(240, 240, 240), width=5)  # 车位线
    if bay == "empty":
        return im
    d.rounded_rectangle([160, 180, 360, 260], 12, fill=(120, 120, 135))  # 车
    d.rounded_rectangle([170, 250, 250, 258], 3, fill=(40, 40, 40))  # 轮
    d.rounded_rectangle([260, 250, 350, 258], 3, fill=(40, 40, 40))
    if plate == "blue":  # 蓝色车牌
        d.rectangle([250, 180, 290, 202], fill=(40, 90, 200))
    else:
        d.rectangle([250, 180, 290, 202], fill=(60, 200, 90))
    return im


def _draw_car(d, x0, y, w, color):
    d.rounded_rectangle([x0, y, x0 + w, y + 44], 10, fill=color, outline=(60, 50, 40), width=2)  # 车身
    d.polygon([(x0 + int(w * 0.2), y), (x0 + int(w * 0.38), y - 26), (x0 + int(w * 0.66), y - 26),
               (x0 + int(w * 0.84), y)], fill=color)  # 车顶
    d.polygon([(x0 + int(w * 0.38), y - 22), (x0 + int(w * 0.54), y - 24), (x0 + int(w * 0.52), y),
               (x0 + int(w * 0.3), y)], fill=(70, 80, 100))  # 风挡
    d.rounded_rectangle([x0 + int(w * 0.06), y + 32, x0 + int(w * 0.28), y + 50], 5, fill=(30, 30, 30))
    d.rounded_rectangle([x0 + int(w * 0.64), y + 32, x0 + int(w * 0.86), y + 50], 5, fill=(30, 30, 30))


def vehicle(leaving=False):
    im, d = new_frame()
    if leaving:  # 驶向画面右缘：车头朝右贴边 + 动感线
        _draw_car(d, 296, 196, 205, (160, 95, 60))
        d.line([(330, 180), (296, 148)], fill=(110, 110, 110), width=4)
        d.line([(468, 218), (505, 218)], fill=(110, 110, 110), width=4)
        d.line([(470, 232), (505, 232)], fill=(110, 110, 110), width=4)
    else:  # 停在区域中（广场车位）
        d.rectangle([110, 218, 400, 260], outline=(240, 240, 240), width=5)
        _draw_car(d, 175, 170, 200, (120, 140, 165))
    return im


def ebike(elevator=False):
    im, d = new_frame()
    if elevator:  # 电梯内：灰壁+门缝
        d.rectangle([0, 0, 512, 384], fill=(200, 200, 200))
        d.rectangle([240, 30, 260, 384], fill=(120, 120, 120))  # 门缝
        d.rectangle([30, 300, 480, 384], fill=(170, 168, 164))
    # 电瓶车
    d.ellipse([180, 250, 224, 276], fill=(30, 30, 30))
    d.ellipse([330, 250, 374, 276], fill=(30, 30, 30))
    d.line([(202, 252), (218, 190)], fill=(50, 50, 50), width=6)
    d.line([(350, 252), (330, 190)], fill=(50, 50, 50), width=6)
    d.line([(218, 190), (330, 190)], fill=(50, 50, 50), width=6)
    d.line([(218, 190), (270, 140)], fill=(50, 50, 50), width=6)
    d.rectangle([340, 180, 382, 200], fill=(60, 60, 60))  # 车头
    draw_person(d, 250, 190, dict(stance="sit"))  # 骑手
    return im


def fire(smoke_only=False, flame_only=False):
    im, d = new_frame()
    if not smoke_only:
        d.ellipse([170, 190, 330, 296], fill=(235, 170, 60))  # 地面火光
        for cx, cy, r in [(205, 210, 26), (252, 190, 30), (300, 212, 26)]:  # 火苗
            d.polygon([(cx - r, cy + r), (cx, cy - r), (cx + r, cy + r)], fill=(235, 130, 25))
        d.polygon([(240, 215), (252, 140), (264, 215)], fill=(250, 225, 110))  # 内焰
        d.polygon([(266, 212), (278, 155), (290, 212)], fill=(250, 180, 60))
    if not flame_only:
        for cx, cy, r, c in [(330, 130, 24, (160, 160, 160)), (362, 96, 20, (140, 140, 140)),
                             (395, 132, 24, (165, 165, 165))]:  # 烟团
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
        d.polygon([(350, 100), (330, 40), (376, 80)], fill=(170, 170, 170))  # 烟柱
    return im


def garbage_pile():
    im, d = new_frame()
    for (cx, cy, r, c) in [(160, 230, 40, (140, 120, 70)), (230, 240, 34, (90, 130, 70)),
                           (300, 232, 38, (110, 105, 90)), (190, 200, 26, (160, 150, 100)),
                           (270, 200, 22, (90, 120, 110))]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    return im


def trashbin():
    im, d = new_frame()
    d.rounded_rectangle([200, 150, 320, 260], 10, fill=(40, 140, 80))
    d.rectangle([190, 120, 330, 170], fill=(30, 110, 65), outline=(20, 80, 50), width=4)
    d.ellipse([205, 168, 230, 184], fill=(40, 40, 40))
    d.ellipse([290, 168, 315, 184], fill=(40, 40, 40))
    d.rectangle([230, 150, 290, 170], fill=(200, 220, 200))  # 倾倒口
    return im


def extinguisher():
    im, d = new_frame()
    d.rounded_rectangle([240, 140, 292, 260], 14, fill=(200, 40, 40), outline=(150, 30, 30), width=4)
    d.rectangle([248, 100, 284, 145], fill=(240, 240, 240))  # 喷头
    d.ellipse([244, 122, 288, 152], fill=(235, 235, 235), outline=(150, 150, 150), width=3)
    d.rectangle([258, 90, 274, 104], fill=(60, 60, 60))
    return im


def cone():
    im, d = new_frame()
    d.polygon([(256, 90), (290, 210), (222, 210)], fill=(240, 130, 20))
    d.polygon([(236, 150), (276, 150), (266, 176), (246, 176)], fill=(245, 245, 240))
    d.rectangle([216, 210, 296, 258], fill=(110, 110, 110))
    return im


def hazard():
    im, d = new_frame()
    d.polygon([(256, 90), (330, 160), (256, 230), (182, 160)], fill=(250, 200, 20), outline=(30, 30, 30), width=5)
    d.polygon([(256, 130), (272, 190), (240, 190)], fill=(30, 30, 30))  # 警示图形
    d.line([(273, 205), (322, 205)], fill=(180, 40, 40), width=6)
    return im


def smash_scene():
    im, d = new_frame()
    d.rectangle([205, 120, 251, 166], fill=(70, 70, 80))  # 举起的箱子
    for (x, y, r) in [(150, 210, 12), (190, 240, 9), (320, 230, 11), (360, 250, 8), (280, 210, 10)]:
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=(120, 110, 100))
    draw_person(d, 256, 260, dict(stance="stand", smash=True))
    return im


def phone_scene():
    im, d = new_frame()
    draw_person(d, 256, 260, dict(stance="stand", phone=True))
    return im


def cigarette_scene():
    im, d = new_frame()
    draw_person(d, 256, 260, dict(stance="stand", cigarette=True))
    return im


# ---------------- 算法 → 正/负帧映射 ----------------
def J(**k):
    return k


SCENES = {
    # name: (pos_builder, neg_builder)   —— None 表示共享空房间
    "抽烟检测": (cigarette_scene, lambda: person()),
    "烟火检测": (lambda: fire(), room),
    "室内烟火检测": (lambda: fire(), room),
    "室内白烟火焰检测": (lambda: fire(), room),
    "物品移走检测": (lambda: carrying(True), lambda: carrying(False)),
    "车辆离开": (lambda: vehicle(True), lambda: vehicle(False)),
    "电动车识别": (lambda: ebike(), room),
    "电动车入电梯检测": (lambda: ebike(True), room),
    "非绿牌车辆占用": (lambda: parking("used", "blue"), lambda: parking("empty", None)),
    "垃圾堆放检测": (garbage_pile, room),
    "垃圾桶检测": (trashbin, room),
    "灭火器检测": (extinguisher, room),
    "锥形桶检测": (cone, room),
    "危险货物标签识别": (hazard, room),
    "离岗检测": (room, lambda: desk("manned")),
    "打架检测": (lambda: two_people(True), lambda: person()),
    "安全帽检测": (lambda: person(helmet=True), lambda: person()),
    "安全帽扣检测": (lambda: person(helmet=True, seatbelt=True), lambda: person(helmet=True)),
    "安全带检测": (lambda: person(seatbelt=True), lambda: person()),
    "安全钩检测": (lambda: person(hook=True), lambda: person()),
    "反光衣检测": (lambda: person(vest=True), lambda: person()),
    "绝缘鞋检测": (lambda: person(boots=True), lambda: person()),
    "手套检测": (lambda: person(gloves=True), lambda: person()),
    "厨师服检测": (lambda: person(uniform=True), lambda: person()),
    "厨师帽检测": (lambda: person(chefhat=True), lambda: person()),
    "戴口罩检测": (lambda: person(mask=True), lambda: person()),
    "打电话检测": (phone_scene, lambda: person()),
    "奔跑检测": (lambda: person(stance="run"), lambda: person()),
    "摔倒检测": (lambda: person(stance="lie"), lambda: person()),
    "攀高检测": (climbing, lambda: person()),
    "睡岗检测": (lambda: desk("sleep"), lambda: desk("manned")),
    "砸东西检测": (smash_scene, lambda: person()),
}


# ---------------- LLM 调用（与 LLMUtils.infer 同形态） ----------------
def llm_infer(api_url, api_key, model, prompt, img):
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("缺少 openai: pip install openai 后重试")
    b64 = base64.b64encode(to_png_bytes(img)).decode()
    client = OpenAI(api_key=api_key or "sk-none", base_url=api_url, timeout=120)
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return (resp.choices[0].message.content or "").strip().replace("\n", " ")


def evaluate(reply, validate, expect_hit):
    kws = [k.strip() for k in str(validate).split(",") if k.strip()]
    hit = any(k in reply for k in kws)
    return (hit == expect_hit), hit, kws


def trim(s, n=46):
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--name", help="按名称过滤（逗号分隔多选，子串匹配）")
    ap.add_argument("--image", help="用真实帧替代合成正帧（现场校准）")
    ap.add_argument("--only-positive", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--out", help="结果 jsonl 输出路径")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    if a.selfcheck:
        # 安全 token 铁律自检：负面回复不得包含正面关键词
        # 已知坑（保留此断言防回归）：没有X 含 有X（没有=没+有）；未X 含 X。
        #   故负面必须走契约 token（正常/未X），validate 只放正面 token。
        assert evaluate("未吸烟", "在吸烟", True) == (False, False, ["在吸烟"])  # 未吸烟 ⊉ 在吸烟
        assert evaluate("未戴", "已戴", True) == (False, False, ["已戴"])       # 未戴 ⊉ 已戴
        assert evaluate("正常", "有火,有烟", False) == (True, False, ["有火", "有烟"])
        assert evaluate("正常", "有灭火器", True) == (False, False, ["有灭火器"])
        assert evaluate("正常", "斗殴", True) == (False, False, ["斗殴"])
        assert evaluate("在吸烟", "在吸烟", True) == (True, True, ["在吸烟"])
        assert evaluate("有火", "有火,有烟", True) == (True, True, ["有火", "有烟"])
        # 已知假阳性样本（契约外回复）：没有灭火器 ⊃ 有灭火器 → 绝不允许负面回这种话术
        assert evaluate("没有灭火器", "有灭火器", False) == (False, True, ["有灭火器"])
        print("selfcheck OK")
        return

    db = os.path.abspath(os.path.expanduser(a.db))
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    llm = cur.execute("SELECT api_url, api_key, model_name FROM av_llm WHERE id=1").fetchone()
    if not llm:
        sys.exit("av_llm 无记录")
    api_url, api_key, model = llm
    rows = cur.execute(
        "SELECT name, llm_prompt, llm_validate FROM av_biz_algorithm "
        "WHERE llm_id IS NOT NULL AND llm_prompt != '' AND state=1 ORDER BY id"
    ).fetchall()
    if a.name:
        names = [n.strip() for n in a.name.split(",") if n.strip()]
        rows = [r for r in rows if any(nm in r[0] for nm in names)]
    print(f"共 {len(rows)} 条 LLM 算法待校准  [{api_url} / {model}]")
    if a.max:
        rows = rows[: a.max]

    n_pass = n_fail = 0
    lines = []
    for name, prompt, validate in rows:
        if name not in SCENES and not a.image:
            print(f"[SKIP] {name}: 无合成场景（请用 --image 现场帧）")
            continue
        for kind, builder in (("pos", None), ("neg", None)):
            if a.only_positive and kind == "neg":
                continue
            if a.image and kind == "pos":
                img = Image.open(a.image).convert("RGB")
            elif kind == "pos":
                img = SCENES[name][0]()
            else:
                img = SCENES[name][1]()
            reply = llm_infer(api_url, api_key, model, prompt, img)
            expect = (kind == "pos")
            ok, hit, kws = evaluate(reply, validate, expect)
            tag = "PASS" if ok else "FAIL"
            if ok:
                n_pass += 1
            else:
                n_fail += 1
            rec = {"name": name, "kind": kind, "reply": reply, "validate": validate,
                   "expect_hit": expect, "hit": hit}
            lines.append(rec)
            print(f"[{tag}] {name} {kind:>3} 回复:「{trim(reply)}」 validate={kws} expect_hit={expect} hit={hit}")
    print(f"\n=== {n_pass} PASS / {n_fail} FAIL ===")
    if a.out:
        import json
        with open(a.out, "w") as f:
            for r in lines:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("结果已存:", a.out)


if __name__ == "__main__":
    main()
