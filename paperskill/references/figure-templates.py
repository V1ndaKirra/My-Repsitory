# -*- coding: utf-8 -*-
"""Reference figure templates (example system).

These functions are kept as CODE TEMPLATES ONLY.  They contain
example project data.  To generate figures for a
different project, write your own functions in project/custom_figures.py
using the drawing primitives from scripts/assets_generate_figures.py.

Primitives available (import from assets_generate_figures):
  box, arrow, arrow_v, arrow_h, draw_entity, draw_relation,
  draw_flow_node, draw_section_label, new_figure, save_figure,
  BLUE, LBLUE, GRAY, LGRAY, ORANGE, LORANGE, GREEN, LGREEN, RED, LRED

Pattern for custom_figures.py:

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from assets_generate_figures import (
        box, arrow, draw_entity, draw_relation,
        new_figure, save_figure, update_manifest,
        BLUE, LBLUE, GRAY, LGRAY, ORANGE, LORANGE, GREEN, LGREEN,
    )

    def my_arch_overview(path):
        fig, ax = new_figure(figsize=(10, 6.2))
        box(ax, 0.3, 5.0, 4.5, 1.0, "前端 ...", LORANGE, ORANGE, 11, True)
        # ... more drawing calls ...
        save_figure(fig, path)

    if __name__ == "__main__":
        my_arch_overview(sys.argv[1] if len(sys.argv) > 1 else "output.png")
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon

# Inlined primitives for standalone usage of this template file
BLUE = "#2F5597"; LBLUE = "#D9E2F3"; GRAY = "#595959"; LGRAY = "#F2F2F2"
ORANGE = "#C55A11"; LORANGE = "#FCE4D6"; GREEN = "#548235"; LGREEN = "#E2EFDA"
RED = "#C0392B"; LRED = "#FCE4E4"

def _box(ax, x, y, w, h, text, fc=LBLUE, ec=BLUE, fs=11, bold=False):
    p = FancyBboxPatch((x,y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                        lw=1.2, ec=ec, fc=fc)
    ax.add_patch(p)
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs, color="#1F1F1F",
            fontweight="bold" if bold else "normal")

def _arrow(ax, x1, y1, x2, y2, c=GRAY, style="->", lw=1.1):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2), arrowstyle=style, mutation_scale=12, lw=lw, color=c))


# ─── TEMPLATE 1: Architecture Overview ─────────────────────────

def fig_arch_overview(path):
    """System architecture diagram (4-layer: frontend / app / security / data)."""
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=200)
    ax.set_xlim(0, 10); ax.set_ylim(0, 6.2); ax.axis("off")
    _box(ax, 0.3, 5.0, 4.5, 1.0, "管理端前端 admin-web\n(Vue 3 + Vite)", LORANGE, ORANGE, 11, True)
    _box(ax, 5.2, 5.0, 4.5, 1.0, "用户端前端 client-web\n(Vue 3 + Vite)", LORANGE, ORANGE, 11, True)
    _box(ax, 0.3, 3.4, 9.4, 1.3,
         "后端服务 app-server (Spring Boot)\n控制层 Controller · 业务层 Service · 数据访问层 Mapper",
         LBLUE, BLUE, 11, True)
    _box(ax, 3.2, 2.0, 3.6, 0.9, "Spring Security + JWT 认证鉴权", LGREEN, GREEN, 10.5)
    _box(ax, 3.2, 0.5, 3.6, 1.0, "MySQL 数据库\n(user / product / order /\nrecord / payment)",
         LGRAY, GRAY, 10.5, True)
    _arrow(ax, 2.55, 5.0, 2.55, 4.7)
    _arrow(ax, 7.45, 5.0, 7.45, 4.7)
    _arrow(ax, 5.0, 3.4, 5.0, 2.9)
    _arrow(ax, 5.0, 2.0, 5.0, 1.5)
    ax.text(0.3, 6.02, "前端层", fontsize=10, color=ORANGE, fontweight="bold")
    ax.text(0.3, 4.72, "应用层", fontsize=10, color=BLUE, fontweight="bold")
    ax.text(0.3, 2.92, "安全层", fontsize=10, color=GREEN, fontweight="bold")
    ax.text(0.3, 1.52, "数据层", fontsize=10, color=GRAY, fontweight="bold")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ─── TEMPLATE 2: Module Overview ───────────────────────────────

def fig_module_overview(path):
    """Functional module tree diagram."""
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200)
    ax.set_xlim(0, 10); ax.set_ylim(0, 5.6); ax.axis("off")
    _box(ax, 3.5, 4.6, 3.0, 0.7, "业务管理系统", LBLUE, BLUE, 12, True)
    for name, x in [("商品管理",0.3),("库存管理",1.55),("订单管理",2.8),("统计看板",4.05)]:
        _box(ax, x, 3.1, 1.15, 0.75, name, LORANGE, ORANGE, 10)
    _box(ax, 0.3, 3.9, 4.9, 0.5, "管理端业务模块", LORANGE, ORANGE, 10, True)
    for name, x in [("注册登录",5.3),("商品浏览",6.55),("下单支付",7.8),("订单查询",9.05)]:
        _box(ax, x-0.1, 3.1, 1.15, 0.75, name, LGREEN, GREEN, 10)
    _box(ax, 5.2, 3.9, 4.6, 0.5, "用户端业务模块", LGREEN, GREEN, 10, True)
    for name, x in [("AuthService",0.6),("OrderService",2.4),("ProductService",5.2),("CategoryService",7.0)]:
        _box(ax, x, 0.85, 2.3, 0.7, name, "white", BLUE, 10)
    _box(ax, 0.3, 1.7, 9.4, 0.5, "后端核心服务模块", LBLUE, BLUE, 10, True)
    _box(ax, 0.3, 0.1, 9.4, 0.5, "数据访问层 Mapper + MySQL 存储", LGRAY, GRAY, 10, True)
    _arrow(ax, 5.0, 4.6, 5.0, 4.4)
    _arrow(ax, 2.75, 3.9, 2.75, 2.2)
    _arrow(ax, 7.5, 3.9, 7.5, 2.2)
    _arrow(ax, 5.0, 1.7, 5.0, 0.6)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ─── TEMPLATE 3: E-R Diagram ───────────────────────────────────

def fig_er_diagram(path):
    """Entity-Relationship diagram."""
    fig, ax = plt.subplots(figsize=(10, 6.4), dpi=200)
    ax.set_xlim(0, 10); ax.set_ylim(0, 6.4); ax.axis("off")
    entities = {
        "sys_user":       (0.4, 4.9, 2.3, 1.1, ["user_id (PK)", "username", "password", "role"]),
        "product_type":   (7.3, 4.9, 2.3, 1.1, ["type_id (PK)", "name", "price", "stock"]),
        "product":        (7.3, 2.9, 2.3, 1.1, ["prod_id (PK)", "type_id (FK)", "status"]),
        "order_info":     (3.85, 2.9, 2.3, 1.35, ["order_id (PK)", "user_id (FK)", "prod_id (FK)", "type_id (FK)", "status", "create_time"]),
        "record_info":    (0.4, 0.5, 2.3, 1.1, ["record_id (PK)", "order_id (FK)", "start_time", "end_time"]),
        "payment_record": (7.3, 0.5, 2.3, 1.1, ["pay_id (PK)", "order_id (FK)", "amount", "pay_time"]),
    }
    for name, (x, y, w, h, fields) in entities.items():
        _box(ax, x, y+h-0.35, w, 0.35, name, BLUE, BLUE, 11, True)
        ax.text(x+w/2, y+h-0.18, name, ha="center", va="center", color="white", fontsize=11, fontweight="bold")
        ax.add_patch(Rectangle((x, y), w, h-0.35, facecolor="white", edgecolor=BLUE, linewidth=1.1))
        for i, f in enumerate(fields):
            ax.text(x+0.1, y+h-0.55-i*0.18, f, fontsize=9, color="#1F1F1F", va="center")
    rels = [
        ("sys_user","order_info","1","N","下单"), ("product_type","product","1","N","分类"),
        ("product","order_info","1","N","包含"), ("product_type","order_info","1","N","计价"),
        ("order_info","record_info","1","1","记录"), ("order_info","payment_record","1","1","支付"),
    ]
    def _c(e): x,y,w,h,_=entities[e]; return x+w/2, y+h/2
    for a,b,ca,cb,label in rels:
        x1,y1=_c(a); x2,y2=_c(b)
        _arrow(ax,x1,y1,x2,y2,c=GRAY,style="-",lw=1.0)
        mx,my=(x1+x2)/2,(y1+y2)/2
        ax.text(mx,my+0.05,f"{ca}:{cb}",fontsize=9,color=ORANGE,ha="center",va="center",
                bbox=dict(boxstyle="round,pad=0.15",fc="white",ec="none"))
        ax.text(mx,my-0.2,label,fontsize=8.5,color=GRAY,ha="center",va="center")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ─── TEMPLATE 4: Order Status Flow ─────────────────────────────

def fig_order_flow(path):
    """Business process flowchart (order lifecycle)."""
    ROSE_FILL="#FCE4E4"; ROSE_EDGE="#C0392B"; PROC_FILL="#FFFFFF"; PROC_EDGE="#2E75B6"
    ARROW_CLR="#1F4E79"; TEXT_CLR="#1F1F1F"
    fig, ax = plt.subplots(figsize=(8.5, 11.0), dpi=200)
    ax.set_xlim(0, 9); ax.set_ylim(0, 11.6); ax.axis("off")
    BW, BH = 3.4, 0.62; MX = 1.5; MCX = MX+BW/2; CW=2.7; CX=5.4; CCX=CX+CW/2
    def _r(cx,cy,w,h,t,fill=PROC_FILL,edge=PROC_EDGE):
        ax.add_patch(Rectangle((cx-w/2,cy-h/2),w,h,lw=1.15,ec=edge,fc=fill))
        ax.text(cx,cy,t,ha="center",va="center",fontsize=10.5,color=TEXT_CLR,family="SimSun")
    def _ro(cx,cy,w,h,t,fill,edge):
        ax.add_patch(FancyBboxPatch((cx-w/2,cy-h/2),w,h,boxstyle="round,pad=0.015,rounding_size=0.28",lw=1.3,ec=edge,fc=fill))
        ax.text(cx,cy,t,ha="center",va="center",fontsize=11,color=TEXT_CLR,family="SimSun")
    def _pa(cx,cy,w,h,t,fill=PROC_FILL,edge=PROC_EDGE):
        x0=cx-w/2; y0=cy-h/2; sk=0.28
        ax.add_patch(Polygon([(x0+sk,y0),(x0+w,y0),(x0+w-sk,y0+h),(x0,y0+h)],closed=True,lw=1.15,ec=edge,fc=fill))
        ax.text(cx,cy,t,ha="center",va="center",fontsize=10.5,color=TEXT_CLR,family="SimSun")
    nodes = [("start","开始"),("para","用户登录并提交订单"),("rect","订单状态：待支付"),
             ("rect","用户完成支付"),("rect","订单状态：已支付"),("rect","管理员确认订单"),
             ("rect","订单状态：处理中"),("rect","管理员完成处理"),("rect","订单状态：已完成"),("end","结束")]
    yt=11.0; gap=0.98; my=[yt-i*gap for i in range(len(nodes))]
    for (k,t),cy in zip(nodes,my):
        if k in ("start","end"): _ro(MCX,cy,BW,BH,t,ROSE_FILL,ROSE_EDGE)
        elif k=="para": _pa(MCX,cy,BW,BH,t)
        else: _r(MCX,cy,BW,BH,t)
    for i in range(len(nodes)-1):
        ax.add_patch(FancyArrowPatch((MCX,my[i]-BH/2),(MCX,my[i+1]+BH/2),arrowstyle="->",mutation_scale=14,lw=1.15,color=ARROW_CLR))
    _r(CCX,my[2],CW,BH,"订单状态：已取消")
    ax.add_patch(FancyArrowPatch((MX+BW,my[2]),(CX,my[2]),arrowstyle="->",mutation_scale=14,lw=1.15,color=ARROW_CLR))
    ax.text((MX+BW+CX)/2,my[2]+0.32,"取消订单",ha="center",va="bottom",fontsize=9,color="#666666",family="SimSun")
    ax.add_patch(FancyArrowPatch((CCX,my[2]-BH/2),(MX+BW,my[-1]),connectionstyle="angle,angleA=-90,angleB=0,rad=0",arrowstyle="->",mutation_scale=14,lw=1.15,color=ARROW_CLR))
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
