# -*- coding: utf-8 -*-
"""Generate a Chinese Chen-style ER diagram from thesis profile.json.

Usage:
  python generate_chen_er_from_profile.py \
    --profile E:\\path\\to\\profile.json \
    --png-out E:\\path\\to\\er-chen-cn.png \
    --svg-out E:\\path\\to\\er-chen-cn.svg
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Ellipse, Polygon

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False

ENTITY_NAME_MAP = {
    "SysUser": "用户",
    "SysRole": "角色",
    "SysUserRole": "用户角色关联",
    "ProductType": "商品类型",
    "Product": "商品",
    "OrderInfo": "订单",
    "RecordInfo": "操作记录",
    "PaymentRecord": "支付记录",
}

FIELD_NAME_MAP = {
    "id": "编号",
    "username": "用户名",
    "password": "密码",
    "nickname": "昵称",
    "phone": "手机号",
    "status": "状态",
    "create_time": "创建时间",
    "role_name": "角色名称",
    "role_code": "角色编码",
    "user_id": "用户编号",
    "role_id": "角色编号",
    "type_name": "类型名称",
    "price": "价格",
    "capacity": "容量",
    "description": "描述",
    "image_url": "图片地址",
    "prod_no": "商品编号",
    "type_id": "类型编号",
    "order_no": "订单号",
    "customer_name": "客户姓名",
    "customer_phone": "客户电话",
    "prod_id": "商品编号",
    "order_date": "下单日期",
    "delivery_date": "交付日期",
    "total_amount": "总金额",
    "order_id": "订单编号",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "deposit": "押金",
    "extra_cost": "额外费用",
    "final_amount": "最终金额",
    "pay_type": "支付方式",
    "pay_amount": "支付金额",
    "pay_time": "支付时间",
}

PRIMARY_FIELDS = {
    "SysUser": {"id": "用户编号"},
    "SysRole": {"id": "角色编号"},
    "SysUserRole": {"id": "关联编号"},
    "ProductType": {"id": "类型编号"},
    "Product": {"id": "商品编号"},
    "OrderInfo": {"id": "订单编号"},
    "RecordInfo": {"id": "记录编号"},
    "PaymentRecord": {"id": "支付编号"},
}

ENTITY_FIELD_OVERRIDES = {
    "SysUser": {
        "status": "用户状态",
        "create_time": "注册时间",
    },
    "ProductType": {
        "price": "商品价格",
        "capacity": "库存容量",
        "description": "商品描述",
        "image_url": "商品图片",
    },
    "Product": {
        "status": "商品状态",
    },
    "OrderInfo": {
        "status": "订单状态",
        "create_time": "下单时间",
    },
}

# 为了避免论文插图过于拥挤，这里只保留每个实体最核心的字段。
# 优先级：主键 > 关键业务字段 > 少量必要外键。
ENTITY_KEEP_FIELDS = {
    "ProductType": ["id", "type_name", "price", "capacity"],
    "Product": ["id", "prod_no", "status"],
    "OrderInfo": ["id", "customer_name", "order_date", "delivery_date", "status", "total_amount"],
    "RecordInfo": ["id", "start_time", "end_time", "final_amount"],
    "PaymentRecord": ["id", "pay_type", "pay_amount", "pay_time"],
}

REL_CONFIG = [
    ("ProductType", "Product", "定义", "1", "N", (11.9, 12.7)),
    ("ProductType", "OrderInfo", "对应商品", "1", "N", (8.7, 8.5)),
    ("Product", "OrderInfo", "包含商品", "1", "N", (14.5, 8.2)),
    ("OrderInfo", "RecordInfo", "生成", "1", "N", (8.0, 4.2)),
    ("OrderInfo", "PaymentRecord", "产生", "1", "N", (14.6, 4.2)),
]

LAYOUT = {
    "ProductType":   {"center": (8.0, 11.8), "size": (2.1, 0.9), "arc": (105, 255), "radius": (2.5, 1.8)},
    "Product":       {"center": (15.8, 11.8), "size": (2.0, 0.9), "arc": (-55, 175), "radius": (2.4, 1.6)},
    "OrderInfo":     {"center": (11.8, 6.4), "size": (2.6, 0.9), "arc": (20, 340),  "radius": (4.0, 2.45)},
    "RecordInfo":    {"center": (6.8, 2.0), "size": (2.4, 0.9), "arc": (170, 335), "radius": (2.6, 1.55)},
    "PaymentRecord": {"center": (16.9, 2.0), "size": (2.4, 0.9), "arc": (15, 180),  "radius": (2.6, 1.5)},
}

COLORS = {
    "entity_fill": "#F8CBAD",
    "entity_edge": "#C55A11",
    "attr_fill": "#D9EAF7",
    "attr_edge": "#5B9BD5",
    "pk_fill": "#FFF2CC",
    "pk_edge": "#BF9000",
    "fk_fill": "#E2F0D9",
    "fk_edge": "#70AD47",
    "rel_fill": "#E4DFEC",
    "rel_edge": "#8064A2",
    "line": "#666666",
    "text": "#1F1F1F",
}


def cn_entity_name(name: str) -> str:
    return ENTITY_NAME_MAP.get(name, name)


def cn_field_name(entity_name: str, field_name: str, is_pk: bool) -> str:
    if is_pk and field_name in PRIMARY_FIELDS.get(entity_name, {}):
        return PRIMARY_FIELDS[entity_name][field_name]
    if field_name in ENTITY_FIELD_OVERRIDES.get(entity_name, {}):
        return ENTITY_FIELD_OVERRIDES[entity_name][field_name]
    return FIELD_NAME_MAP.get(field_name, field_name)


def get_fk_fields(entity: dict) -> set[str]:
    return {rel.get("fk") for rel in entity.get("relations", []) if rel.get("fk")}


def estimate_ellipse_size(label: str) -> tuple[float, float]:
    cjk = sum(1 for ch in label if '\u4e00' <= ch <= '\u9fff')
    ascii_count = len(label) - cjk
    width = min(max(1.45 + cjk * 0.22 + ascii_count * 0.10, 1.75), 3.6)
    height = 0.62 if len(label) <= 7 else 0.70
    return width, height


def rect_border_point(cx: float, cy: float, w: float, h: float, tx: float, ty: float) -> tuple[float, float]:
    dx, dy = tx - cx, ty - cy
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return cx, cy
    sx = (w / 2) / abs(dx) if abs(dx) > 1e-6 else float("inf")
    sy = (h / 2) / abs(dy) if abs(dy) > 1e-6 else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def ellipse_border_point(cx: float, cy: float, w: float, h: float, tx: float, ty: float) -> tuple[float, float]:
    dx, dy = tx - cx, ty - cy
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return cx, cy
    a, b = w / 2, h / 2
    denom = math.sqrt((dx * dx) / (a * a) + (dy * dy) / (b * b))
    return cx + dx / denom, cy + dy / denom


def diamond_border_point(cx: float, cy: float, w: float, h: float, tx: float, ty: float) -> tuple[float, float]:
    dx, dy = tx - cx, ty - cy
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return cx, cy
    sx = (w / 2) / abs(dx) if abs(dx) > 1e-6 else float("inf")
    sy = (h / 2) / abs(dy) if abs(dy) > 1e-6 else float("inf")
    s = 1 / (abs(dx) / (w / 2) + abs(dy) / (h / 2))
    return cx + dx * s, cy + dy * s


def arc_points(center: tuple[float, float], n: int, rx: float, ry: float, start_deg: float, end_deg: float):
    cx, cy = center
    span = end_deg - start_deg
    if n == 1:
        angles = [(start_deg + end_deg) / 2]
    elif abs(abs(span) - 360) < 1e-6:
        angles = [start_deg + span * i / n for i in range(n)]
    else:
        angles = [start_deg + span * i / (n - 1) for i in range(n)]
    pts = []
    for deg in angles:
        rad = math.radians(deg)
        pts.append((cx + rx * math.cos(rad), cy + ry * math.sin(rad)))
    return pts


def draw_entity(ax, center, size, label):
    cx, cy = center
    w, h = size
    rect = Rectangle((cx - w / 2, cy - h / 2), w, h,
                     linewidth=1.7, edgecolor=COLORS["entity_edge"], facecolor=COLORS["entity_fill"], zorder=3)
    ax.add_patch(rect)
    ax.text(cx, cy, label, ha="center", va="center", fontsize=12, color=COLORS["text"], fontweight="bold", zorder=4)
    return w, h


def draw_attribute(ax, center, label, attr_type="normal"):
    cx, cy = center
    w, h = estimate_ellipse_size(label)
    fill = COLORS["attr_fill"]
    edge = COLORS["attr_edge"]
    if attr_type == "pk":
        fill, edge = COLORS["pk_fill"], COLORS["pk_edge"]
    elif attr_type == "fk":
        fill, edge = COLORS["fk_fill"], COLORS["fk_edge"]
    ell = Ellipse((cx, cy), w, h, linewidth=1.3, edgecolor=edge, facecolor=fill, zorder=2)
    ax.add_patch(ell)
    ax.text(cx, cy, label, ha="center", va="center", fontsize=9.4, color=COLORS["text"], zorder=3)
    return w, h


def draw_relationship(ax, center, label):
    cx, cy = center
    w, h = 1.55, 0.85
    pts = [(cx, cy + h / 2), (cx - w / 2, cy), (cx, cy - h / 2), (cx + w / 2, cy)]
    diamond = Polygon(pts, closed=True, linewidth=1.5, edgecolor=COLORS["rel_edge"], facecolor=COLORS["rel_fill"], zorder=3)
    ax.add_patch(diamond)
    ax.text(cx, cy, label, ha="center", va="center", fontsize=10, color=COLORS["text"], zorder=4)
    return w, h


def draw_connector(ax, p1, p2, lw=1.0):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=COLORS["line"], linewidth=lw, zorder=1)


def draw_cardinality(ax, p_entity, p_rel, card):
    x = p_entity[0] * 0.72 + p_rel[0] * 0.28
    y = p_entity[1] * 0.72 + p_rel[1] * 0.28
    ax.text(x, y, card, fontsize=10, color="#9E480E", fontweight="bold",
            ha="center", va="center", zorder=5,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.95))


def build_entities(profile: dict):
    entities = {e["name"]: e for e in profile["data_model"]["entities"]}
    return entities


def convert_fields(entity_name: str, entity: dict):
    fk_fields = get_fk_fields(entity)
    keep = ENTITY_KEEP_FIELDS.get(entity_name)
    keep_index = {name: idx for idx, name in enumerate(keep)} if keep else {}
    items = []
    for field in entity.get("fields", []):
        fname = field.get("name")
        if keep and fname not in keep:
            continue
        label = cn_field_name(entity_name, fname, bool(field.get("pk")))
        attr_type = "pk" if field.get("pk") else ("fk" if fname in fk_fields else "normal")
        items.append({"label": label, "type": attr_type, "source": fname})
    if keep:
        items.sort(key=lambda x: keep_index.get(x["source"], 999))
    return items


def draw_legend(ax):
    base_x = 21.1
    base_y = 0.95
    labels = [("主键字段", "pk"), ("外键字段", "fk"), ("普通字段", "normal")]
    ax.text(base_x, base_y + 0.9, "图例", fontsize=10.5, fontweight="bold", color=COLORS["text"])
    for i, (label, kind) in enumerate(labels):
        cy = base_y + 0.55 - i * 0.48
        w, h = estimate_ellipse_size(label)
        fill = COLORS["attr_fill"]
        edge = COLORS["attr_edge"]
        if kind == "pk":
            fill, edge = COLORS["pk_fill"], COLORS["pk_edge"]
        elif kind == "fk":
            fill, edge = COLORS["fk_fill"], COLORS["fk_edge"]
        ax.add_patch(Ellipse((base_x + 0.8, cy), 1.1, 0.45, linewidth=1.1, edgecolor=edge, facecolor=fill))
        ax.text(base_x + 2.0, cy, label, fontsize=8.8, va="center", ha="left", color=COLORS["text"])


def generate(profile_path: str, png_out: str, svg_out: str | None = None):
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    entities = build_entities(profile)

    fig, ax = plt.subplots(figsize=(18.8, 10.8), dpi=220)
    ax.set_xlim(-0.8, 25.4)
    ax.set_ylim(-0.6, 15.0)
    ax.axis("off")

    # draw entities first
    entity_bounds = {}
    attr_bounds = {}
    for ename, cfg in LAYOUT.items():
        entity = entities.get(ename)
        if not entity:
            continue
        center = cfg["center"]
        size = cfg["size"]
        draw_entity(ax, center, size, cn_entity_name(ename))
        entity_bounds[ename] = {"center": center, "size": size}

        attrs = convert_fields(ename, entity)
        pts = arc_points(center, len(attrs), cfg["radius"][0], cfg["radius"][1], cfg["arc"][0], cfg["arc"][1])
        attr_bounds[ename] = []
        for attr, pt in zip(attrs, pts):
            aw, ah = draw_attribute(ax, pt, attr["label"], attr["type"])
            attr_bounds[ename].append({"center": pt, "size": (aw, ah)})
            p1 = rect_border_point(center[0], center[1], size[0], size[1], pt[0], pt[1])
            p2 = ellipse_border_point(pt[0], pt[1], aw, ah, center[0], center[1])
            draw_connector(ax, p1, p2, lw=0.95)

    # draw relationships
    for a, b, label, card_a, card_b, rel_center in REL_CONFIG:
        if a not in entity_bounds or b not in entity_bounds:
            continue
        rw, rh = draw_relationship(ax, rel_center, label)
        ac = entity_bounds[a]["center"]
        bc = entity_bounds[b]["center"]
        aw, ah = entity_bounds[a]["size"]
        bw, bh = entity_bounds[b]["size"]

        a_from = rect_border_point(ac[0], ac[1], aw, ah, rel_center[0], rel_center[1])
        a_to = diamond_border_point(rel_center[0], rel_center[1], rw, rh, ac[0], ac[1])
        b_from = rect_border_point(bc[0], bc[1], bw, bh, rel_center[0], rel_center[1])
        b_to = diamond_border_point(rel_center[0], rel_center[1], rw, rh, bc[0], bc[1])

        draw_connector(ax, a_from, a_to, lw=1.05)
        draw_connector(ax, b_from, b_to, lw=1.05)
        draw_cardinality(ax, a_from, a_to, card_a)
        draw_cardinality(ax, b_from, b_to, card_b)

    draw_legend(ax)

    Path(os.path.dirname(png_out)).mkdir(parents=True, exist_ok=True)
    fig.savefig(png_out, bbox_inches="tight", pad_inches=0.30, facecolor="white")
    if svg_out:
        fig.savefig(svg_out, bbox_inches="tight", pad_inches=0.30, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--png-out", required=True)
    parser.add_argument("--svg-out", default=None)
    args = parser.parse_args()
    generate(args.profile, args.png_out, args.svg_out)
    print(f"[ok] png -> {args.png_out}")
    if args.svg_out:
        print(f"[ok] svg -> {args.svg_out}")


if __name__ == "__main__":
    main()
