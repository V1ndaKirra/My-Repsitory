# -*- coding: utf-8 -*-
"""Thesis figure rendering toolkit.

Usage:
  - Import the drawing primitives (_box, _arrow, draw_entity, etc.) in your
    custom figure scripts.
  - Or run directly: reads project/figures-config.json, maps each job to a
    drawing function (from this file or from project/custom_figures.py), and
    updates assets/manifest.json.

Example project figures have been moved to
references/figure-templates.py as reference templates.  In Phase 5, the agent
should inspect project/profile.json and write a project/custom_figures.py that
defines project-specific drawing functions using the primitives below.
"""
import json
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.environ.get("THESIS_ROOT", ROOT)
FIG_DIR = os.path.join(ROOT, "assets", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["font.serif"] = ["SimSun"]
plt.rcParams["axes.unicode_minus"] = False

# ── color palette ──────────────────────────────────────────────
BLUE   = "#2F5597"
LBLUE  = "#D9E2F3"
GRAY   = "#595959"
LGRAY  = "#F2F2F2"
ORANGE = "#C55A11"
LORANGE = "#FCE4D6"
GREEN  = "#548235"
LGREEN = "#E2EFDA"
RED    = "#C0392B"
LRED   = "#FCE4E4"

# ── drawing primitives ─────────────────────────────────────────

def box(ax, x, y, w, h, text, facecolor=LBLUE, edgecolor=BLUE,
        fontsize=11, bold=False, text_color="#1F1F1F"):
    """Draw a rounded box with centered text."""
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2, edgecolor=edgecolor, facecolor=facecolor,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text,
            ha="center", va="center",
            fontsize=fontsize, color=text_color,
            fontweight="bold" if bold else "normal")
    return patch


def arrow(ax, x1, y1, x2, y2, color=GRAY, style="->", lw=1.1):
    """Draw an arrow from (x1,y1) to (x2,y2)."""
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=12,
        linewidth=lw, color=color))


# ── text measurement ───────────────────────────────────────────

def measure_text_bbox(ax, text, fontsize=10.5, family="SimSun"):
    """Measure text bounding box in data coordinates.
    Returns (width, height) in axes units."""
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    if renderer is None:
        # Fallback: rough estimate (Chinese char ≈ fontsize, ASCII ≈ 0.5*fontsize)
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f')
        ascii_count = len(text) - cjk_count
        w_est = (cjk_count * fontsize + ascii_count * fontsize * 0.55) / 72  # points to inches
        h_est = fontsize * 1.4 / 72
        trans = ax.transData.inverted()
        w_data = trans.transform([(w_est, 0)])[0][0] - trans.transform([(0, 0)])[0][0]
        h_data = trans.transform([(0, h_est)])[0][1] - trans.transform([(0, 0)])[0][1]
        return max(w_data, 0.5), max(h_data, 0.3)
    t = ax.text(0, 0, text, fontsize=fontsize, family=family, alpha=0)
    bbox = t.get_window_extent(renderer)
    t.remove()
    inv = ax.transData.inverted()
    [[x0, y0], [x1, y1]] = inv.transform(bbox)
    return x1 - x0, y1 - y0


def auto_fit_box(ax, cx, cy, text, min_w=1.2, min_h=0.5, padding=0.25,
                 facecolor=LBLUE, edgecolor=BLUE, fontsize=11, bold=False,
                 text_color="#1F1F1F", max_w=5.0):
    """Draw a box that auto-sizes to fit its text, centered at (cx, cy).
    Returns (left, bottom, width, height)."""
    tw, th = measure_text_bbox(ax, text, fontsize)
    # Handle multi-line text
    lines = text.split('\n')
    if len(lines) > 1:
        max_line_w = 0
        for line in lines:
            lw, _ = measure_text_bbox(ax, line, fontsize)
            max_line_w = max(max_line_w, lw)
        tw = max_line_w
        th = th * len(lines) * 1.15
    w = min(max(tw + 2 * padding, min_w), max_w)
    h = max(th + 2 * padding, min_h)
    x, y = cx - w / 2, cy - h / 2
    box(ax, x, y, w, h, text, facecolor, edgecolor, fontsize, bold, text_color)
    return x, y, w, h


# ── diamond node (for flowchart decisions) ─────────────────────

def draw_diamond_node(ax, cx, cy, w, h, text,
                      facecolor="#FCE4D6", edgecolor="#C55A11",
                      fontsize=10.5, text_color="#1F1F1F", bold=False):
    """Draw a diamond-shaped decision node for flowcharts.
    Centered at (cx, cy), width w, height h."""
    x0, y0 = cx - w / 2, cy - h / 2
    pts = [
        (cx, y0 + h),      # bottom
        (x0, cy),           # left
        (cx, y0),           # top
        (x0 + w, cy),       # right
    ]
    patch = Polygon(pts, closed=True,
                    linewidth=1.3, edgecolor=edgecolor,
                    facecolor=facecolor)
    ax.add_patch(patch)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fontsize, color=text_color,
            fontweight="bold" if bold else "normal",
            family="SimSun")
    return patch


# ── existing arrows (keep) ─────────────────────────────────────


def arrow_v(ax, cx, y_top, y_bot, box_h, color=GRAY, lw=1.1):
    """Vertical arrow between two boxes centered at `cx`."""
    arrow(ax, cx, y_top - box_h / 2, cx, y_bot + box_h / 2, color=color, lw=lw)


def arrow_h(ax, y, x_left, x_right, color=GRAY, lw=1.1):
    """Horizontal arrow at `y` from x_left to x_right."""
    arrow(ax, x_left, y, x_right, y, color=color, lw=lw)


def draw_entity(ax, name, x, y, w, h, fields,
                header_color=BLUE, body_color="white", border_color=BLUE,
                text_color="#1F1F1F", field_fontsize=9):
    """Draw an ER-diagram entity with header and field rows."""
    header_h = 0.35
    # header
    box(ax, x, y + h - header_h, w, header_h, name,
        facecolor=header_color, edgecolor=header_color,
        fontsize=11, bold=True, text_color="white")
    # body
    ax.add_patch(Rectangle((x, y), w, h - header_h,
                           facecolor=body_color, edgecolor=border_color, linewidth=1.1))
    for i, f in enumerate(fields):
        ax.text(x + 0.1, y + h - header_h - 0.2 - i * 0.18, f,
                fontsize=field_fontsize, color=text_color, va="center")


def draw_relation(ax, entities, a, b, card_a, card_b, label,
                  arrow_color=GRAY, card_color=ORANGE, label_color=GRAY):
    """Draw a relationship line + cardinality + label between two entities."""
    x1, y1, w1, h1, _ = entities[a]
    x2, y2, w2, h2, _ = entities[b]
    cx1, cy1 = x1 + w1 / 2, y1 + h1 / 2
    cx2, cy2 = x2 + w2 / 2, y2 + h2 / 2
    arrow(ax, cx1, cy1, cx2, cy2, color=arrow_color, style="-", lw=1.0)
    mx, my = (cx1 + cx2) / 2, (cy1 + cy2) / 2
    ax.text(mx, my + 0.05, f"{card_a}:{card_b}", fontsize=9, color=card_color,
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.text(mx, my - 0.2, label, fontsize=8.5, color=label_color,
            ha="center", va="center")


def draw_flow_node(ax, cx, cy, w, h, text, kind="rect",
                   proc_edge="#2E75B6", proc_fill="#FFFFFF",
                   term_edge=RED, term_fill=LRED,
                   text_color="#1F1F1F", para_skew=0.28):
    """Draw a flowchart node (round/rect/parallelogram)."""
    if kind in ("start", "end"):
        patch = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle="round,pad=0.015,rounding_size=0.28",
            linewidth=1.3, edgecolor=term_edge, facecolor=term_fill)
    elif kind == "para":
        x0 = cx - w / 2
        y0 = cy - h / 2
        pts = [(x0 + para_skew, y0), (x0 + w, y0),
               (x0 + w - para_skew, y0 + h), (x0, y0 + h)]
        patch = Polygon(pts, closed=True, linewidth=1.15,
                        edgecolor=proc_edge, facecolor=proc_fill)
    else:
        patch = Rectangle((cx - w / 2, cy - h / 2), w, h,
                          linewidth=1.15, edgecolor=proc_edge, facecolor=proc_fill)
    ax.add_patch(patch)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=10.5, color=text_color, family="SimSun")


def draw_section_label(ax, x, y, text, color, fontsize=10):
    """Draw a section label (e.g. '前端层', '应用层') in the left margin."""
    ax.text(x, y, text, fontsize=fontsize, color=color, fontweight="bold")


def new_figure(figsize=(10, 6.2), dpi=200, xlim=(0, 10), ylim=(0, 6.2)):
    """Create a new matplotlib figure/axes with standard thesis settings."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def save_figure(fig, path):
    """Save and close a figure."""
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def update_manifest(jobs, root=None):
    """Generate or update assets/manifest.json with figure entries.
    
    jobs: list of {id, caption, section_ref, file (relative path), size_bytes}
    """
    if root is None:
        root = ROOT
    mf_path = os.path.join(root, "assets", "manifest.json")
    existing = []
    if os.path.exists(mf_path):
        try:
            existing = json.load(open(mf_path, "r", encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing = [a for a in existing if a.get("type") != "figure"]
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries = []
    for j in jobs:
        entries.append({
            "id": j["id"],
            "type": "figure",
            "caption": j["caption"],
            "file": j["file"],
            "source_format": "matplotlib",
            "section_ref": j["section_ref"],
            "profile_version_at_generation": "1.0-draft",
            "size_bytes": j["size_bytes"],
            "generated_at": now_ts,
        })
    merged = existing + entries
    json.dump(merged, open(mf_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return mf_path


# ── main ───────────────────────────────────────────────────────

def main():
    """Read project/figures-config.json, dispatch each job.
    
    Each job entry:
      - id, caption, section_ref (required)
      - type (required): "arch" | "modules" | "er" | "flow" | "custom"
      - For "custom": also provide "module" and "function" to load from
        project/custom_figures.py
    """
    CONFIG_PATH = os.path.join(ROOT, "project", "figures-config.json")
    if not os.path.exists(CONFIG_PATH):
        print(f"[info] No figures-config.json at {CONFIG_PATH}")
        print("Agent should generate project/custom_figures.py and a corresponding")
        print("figures-config.json, then re-run this script.")
        return

    cfg = json.load(open(CONFIG_PATH, "r", encoding="utf-8"))

    # Try to load custom figures module
    custom_mod = None
    custom_path = os.path.join(ROOT, "project", "custom_figures.py")
    if os.path.exists(custom_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("custom_figures", custom_path)
        custom_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(custom_mod)

    # Built-in drawing functions are disabled by default since they contain
    # project-specific example data.  Use project/custom_figures.py instead.
    # To re-enable the old templates for reference, uncomment the import below:
    # from references.figure_templates import (
    #     fig_arch_overview, fig_module_overview,
    #     fig_er_diagram, fig_order_flow,
    # )

    DRAW_FUNCS = {}

    manifest_jobs = []
    for job in cfg:
        aid = job["id"]
        caption = job["caption"]
        section_ref = job["section_ref"]
        ftype = job.get("type", "custom")
        draw_fn = None

        if ftype == "custom":
            mod_name = job.get("module", "custom_figures")
            fn_name = job.get("function", aid.replace("-", "_"))
            if custom_mod and hasattr(custom_mod, fn_name):
                draw_fn = getattr(custom_mod, fn_name)
            else:
                print(f"[warn] custom function '{fn_name}' not found in project/custom_figures.py, skipping {aid}")
                continue
        else:
            print(f"[warn] unknown type '{ftype}' for {aid}; use 'custom' with project/custom_figures.py")
            continue

        out = os.path.join(FIG_DIR, f"{aid}.png")
        draw_fn(out)
        size = os.path.getsize(out)
        manifest_jobs.append({
            "id": aid, "caption": caption, "section_ref": section_ref,
            "file": f"assets/figures/{aid}.png", "size_bytes": size,
        })
        print(f"[ok] {aid} -> {out} ({size} bytes)")

    if manifest_jobs:
        mf = update_manifest(manifest_jobs, root=ROOT)
        print(f"[ok] manifest updated: {mf}")
    else:
        print("[info] no figures generated")


if __name__ == "__main__":
    main()
