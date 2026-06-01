# -*- coding: utf-8 -*-
"""Generate academic diagrams from JSON specs via Graphviz dot.

Supported diagram types: flowchart, architecture, er_diagram, module_tree.

Each diagram is described as a JSON object with type + spec fields.
This script converts the spec to .dot source, shells out to the `dot`
binary, and saves a high-DPI PNG.

Usage:
  python generate_dot_diagrams.py --spec project/figures-spec.json
  python generate_dot_diagrams.py --spec project/figures-spec.json --job fig-order-flow
"""
import json
import os
import subprocess
import sys
import shutil
from datetime import datetime, timezone

ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))
FIG_DIR = os.path.join(ROOT, "assets", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── Graphviz binary detection ──────────────────────────────────

def find_dot_binary():
    """Locate the `dot` binary. Returns path or None."""
    # 1. Explicit path on PATH
    dot = shutil.which("dot")
    if dot:
        return dot
    # 2. Common Graphviz install locations on Windows
    candidates = [
        r"C:\Program Files\Graphviz\bin\dot.exe",
        r"C:\Program Files (x86)\Graphviz\bin\dot.exe",
        os.path.expandvars(r"%USERPROFILE%\scoop\apps\graphviz\current\bin\dot.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


DOT_BIN = find_dot_binary()
DOT_AVAILABLE = DOT_BIN is not None

# ── Color palettes ─────────────────────────────────────────────

PALETTES = {
    "professional": {
        "primary":       "#2F5597",
        "primary_light": "#D9E2F3",
        "accent":        "#C55A11",
        "accent_light":  "#FCE4D6",
        "success":       "#548235",
        "success_light": "#E2EFDA",
        "danger":        "#C0392B",
        "danger_light":  "#FCE4E4",
        "neutral":       "#595959",
        "neutral_light": "#F2F2F2",
        "text":          "#1F1F1F",
        "bg":            "#FFFFFF",
    },
    "clean": {
        "primary":       "#4472C4",
        "primary_light": "#D6E4F0",
        "accent":        "#ED7D31",
        "accent_light":  "#FBE4D5",
        "success":       "#70AD47",
        "success_light": "#E2F0D9",
        "danger":        "#FF6B6B",
        "danger_light":  "#FFE0E0",
        "neutral":       "#7F7F7F",
        "neutral_light": "#EDEDED",
        "text":          "#333333",
        "bg":            "#FFFFFF",
    },
}


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert #RRGGBB to a Graphviz-compatible lighter color.
    Graphviz does NOT support css rgba(). We use the light palette
    colors directly instead for cluster backgrounds."""
    return hex_color  # Alpha is ignored; use *_light palette colors for fills


def palette(theme: str = "professional") -> dict:
    return PALETTES.get(theme, PALETTES["professional"])


# ── Text escaping for dot ──────────────────────────────────────

def dot_escape(s: str) -> str:
    """Escape a string for safe embedding in dot label."""
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def wrap_label(text: str, max_chars: int = 22) -> str:
    """Wrap long label lines before Graphviz rendering.

    Graphviz does not auto-wrap plain labels. Fixed-size nodes will look bad
    unless long technology-stack strings are split into several readable lines.
    This keeps user-provided line breaks and only wraps overly long lines.
    """
    if not text:
        return ""
    wrapped = []
    for raw_line in str(text).split("\n"):
        line = raw_line.strip()
        if len(line) <= max_chars:
            wrapped.append(line)
            continue
        # Do not aggressively split by '+', '/', or '·'. Architecture labels
        # should stay as compact phrases; only wrap when a line is truly long.
        sub_lines = []
        for part in line.split("\n"):
            part = part.strip()
            while len(part) > max_chars:
                sub_lines.append(part[:max_chars].rstrip())
                part = part[max_chars:].lstrip()
            if part:
                sub_lines.append(part)
        wrapped.extend(sub_lines)
    return "\n".join(wrapped)


# ── Graphviz global attributes ─────────────────────────────────

GRAPH_ATTRS = """
  charset="UTF-8";
  fontname="Microsoft YaHei";
  fontsize=11;
  pad=0.5;
  dpi=300;
  bgcolor=white;
"""

NODE_BASE = 'fontname="Microsoft YaHei" fontsize=10.5 margin="0.20,0.14"'

NODE_DEFAULT = f'node [{NODE_BASE}]'

EDGE_ATTRS = 'fontname="Microsoft YaHei" fontsize=9 color="#595959"'

EDGE_DEFAULT = f'edge [{EDGE_ATTRS}]'

# ── Diagram sizing defaults ────────────────────────────────────

DEFAULT_SIZES = {
    # width × height in inches at 72dpi; ratio=auto lets Graphviz keep natural proportions
    # Then rendered at 300dpi for crisp output.  Sizes chosen for A4 paper (≈6.2" text width).
    "flowchart":     'size="6,8"',
    "architecture":  'size="7.5,5.5"',
    "er_diagram":    'size="8,5"',
    "module_tree":   'size="6,9"',
    "timeline":      'size="6,4"',
}

def get_size_attrs(spec: dict, diagram_type: str) -> str:
    """Return size attributes from spec, falling back to type defaults."""
    if spec.get("size"):
        size = spec["size"]
    else:
        size = DEFAULT_SIZES.get(diagram_type, '')
    return size


# ── Builders for each diagram type ─────────────────────────────

def build_flowchart_dot(spec: dict, theme: str = "professional") -> str:
    """Generate dot source for a flowchart.

    spec.nodes: [{"id": "...", "label": "...", "shape": "start|end|process|decision|data|manual", ...}, ...]
    spec.edges: [{"from": "...", "to": "...", "label": "..." | None}, ...]
    spec.direction: "TB" (top-bottom, default) | "LR" (left-right)
    """
    p = palette(theme)
    direction = spec.get("direction", "TB")

    shape_map = {
        "start":    ('oval',           p["danger_light"], p["danger"]),
        "end":      ('oval',           p["danger_light"], p["danger"]),
        "process":  ('box',            p["primary_light"], p["primary"]),
        "decision": ('diamond',        p["accent_light"], p["accent"]),
        "data":     ('parallelogram',  p["neutral_light"], p["neutral"]),
        "manual":   ('box',            p["success_light"], p["success"]),
    }

    lines = [
        "digraph Flowchart {",
        f'  rankdir={direction};',
        f"  newrank=true;",
        f"  nodesep=0.4;",
        f"  ranksep=0.5;",
        f"  {get_size_attrs(spec, 'flowchart')};",
        f"  {GRAPH_ATTRS}",
        "",
        "  /* --- nodes --- */",
    ]

    for node in spec.get("nodes", []):
        nid = node["id"]
        label = dot_escape(node.get("label", nid))
        shape_info = shape_map.get(node.get("shape", "process"),
                                    shape_map["process"])
        gv_shape, fill, border = shape_info
        lines.append(
            f'  {nid} [shape={gv_shape} style=filled '
            f'fillcolor="{fill}" color="{border}" '
            f'fontcolor="{p["text"]}" {NODE_BASE} '
            f'label="{label}"];'
        )

    lines.append("")
    lines.append("  /* --- edges --- */")

    for edge in spec.get("edges", []):
        src = edge["from"]
        dst = edge["to"]
        elabel = dot_escape(edge.get("label", ""))
        if elabel:
            lines.append(f'  {src} -> {dst} [label="{elabel}" {EDGE_ATTRS}];')
        else:
            lines.append(f'  {src} -> {dst} [{EDGE_ATTRS}];')

    lines.append("}")
    return "\n".join(lines)


def build_architecture_dot(spec: dict, theme: str = "professional") -> str:
    """Generate dot source for a layered architecture diagram.

    spec.layers: [{"id": "...", "label": "层名", "color": "primary|accent|success|neutral",
                    "nodes": [{"id": "...", "label": "..."}, ...]}, ...]
    spec.connections: [{"from": "node_id", "to": "node_id"}, ...]
    spec.layer_labels: "inside" | "outside" (default: "outside")
    """
    p = palette(theme)
    direction = spec.get("direction", "TB")

    color_map = {
        "primary": (p["primary"], p["primary_light"]),
        "accent":  (p["accent"], p["accent_light"]),
        "success": (p["success"], p["success_light"]),
        "danger":  (p["danger"], p["danger_light"]),
        "neutral": (p["neutral"], p["neutral_light"]),
    }

    lines = [
        "digraph Architecture {",
        f"  rankdir={direction};",
        f"  newrank=true;",
        f"  splines=ortho;",
        f"  nodesep=0.6;",
        f"  ranksep=0.5;",
        f"  {get_size_attrs(spec, 'architecture')};",
        f"  {GRAPH_ATTRS}",
        "",
    ]

    # Layers as clusters
    for layer in spec.get("layers", []):
        lid = layer["id"]
        llabel = dot_escape(layer.get("label", lid))
        lcolor = color_map.get(layer.get("color", "primary"),
                                color_map["primary"])
        border, bg = lcolor

        lines.append(f"  subgraph cluster_{lid} {{")
        lines.append(f'    label="{llabel}";')
        lines.append(f'    fontname="Microsoft YaHei";')
        lines.append(f'    fontsize=11;')
        lines.append(f'    fontcolor="{border}";')
        lines.append(f'    style="rounded,filled";')
        lines.append(f'    color="{border}";')
        lines.append(f'    fillcolor="{bg}";')
        lines.append(f'    penwidth=1.4;')
        lines.append(f'    margin=14;')
        lines.append(f"    {NODE_DEFAULT};")
        lines.append("")

        node_width = spec.get("node_width", 4.2)
        node_height = spec.get("node_height", 1.15)
        wrap_chars = spec.get("wrap_chars", 50)
        for node in layer.get("nodes", []):
            nid = node["id"]
            nlabel = dot_escape(wrap_label(node.get("label", nid), max_chars=wrap_chars))
            nshape = "box"
            nfill = "white"
            nborder = border
            if node.get("style") == "filled":
                nfill = bg
            node_attrs = (
                f'  {nid} [shape={nshape} style="filled,rounded" '
                f'fixedsize=true width="{node_width}" height="{node_height}" '
                f'fillcolor="{nfill}" color="{nborder}" penwidth=1.2 '
                f'fontcolor="{p["text"]}" label="{nlabel}"];'
            )
            lines.append(node_attrs)

        lines.append("  }")
        lines.append("")

    # Connections
    lines.append("  /* --- connections --- */")
    for conn in spec.get("connections", []):
        src = conn["from"]
        dst = conn["to"]
        lines.append(f'  {src} -> {dst} [{EDGE_ATTRS}];')

    lines.append("}")
    return "\n".join(lines)


def build_er_diagram_dot(spec: dict, theme: str = "professional") -> str:
    """Generate dot source for an Entity-Relationship diagram.

    spec.entities: [{"id": "...", "name": "表名", "fields": [{"name": "...", "pk": bool, "fk": bool}, ...]}, ...]
    spec.relationships: [{"from": "entity_id", "to": "entity_id", "card_a": "1|N", "card_b": "1|N", "label": "关系名"}, ...]
    """
    p = palette(theme)
    direction = spec.get("direction", "LR")

    lines = [
        "digraph ERDiagram {",
        f"  rankdir={direction};",
        f"  newrank=true;",
        f"  nodesep=0.5;",
        f"  ranksep=0.8;",
        f"  {get_size_attrs(spec, 'er_diagram')};",
        f"  {GRAPH_ATTRS}",
        f"  edge [arrowsize=0.8];",
        "",
    ]

    # Entities as HTML-like tables
    for ent in spec.get("entities", []):
        eid = ent["id"]
        ename = dot_escape(ent.get("name", eid))
        fields = ent.get("fields", [])

        # Build HTML table for the entity
        rows = []
        # Header row
        rows.append(
            f'    <tr><td bgcolor="{p["primary"]}">'
            f'<font color="white"><b>{ename}</b></font>'
            f'</td></tr>'
        )
        # Field rows
        for fld in fields:
            fname = dot_escape(fld.get("name", ""))
            markers = []
            if fld.get("pk"):
                markers.append("PK")
            if fld.get("fk"):
                markers.append("FK")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            rows.append(
                f'    <tr><td align="left" bgcolor="white">'
                f'<font color="{p["text"]}">{fname}{marker_str}</font>'
                f'</td></tr>'
            )

        label = '<<table border="1" cellborder="0" cellspacing="0" '
        label += f'cellpadding="4" color="{p["primary"]}">\n'
        label += "\n".join(rows)
        label += "\n</table>>"

        lines.append(f'  {eid} [shape=plaintext label={label}];')

    # Relationships
    lines.append("")
    lines.append("  /* --- relationships --- */")
    for rel in spec.get("relationships", []):
        src = rel["from"]
        dst = rel["to"]
        card_a = rel.get("card_a", "1")
        card_b = rel.get("card_b", "1")
        rlabel = dot_escape(rel.get("label", ""))

        # Cardinality as headlabel / taillabel
        lines.append(
            f'  {src} -> {dst} ['
            f'taillabel="{card_a}" headlabel="{card_b}" '
            f'label="{rlabel}" '
            f'labeldistance=2.5 labelangle=45 '
            f'labelfontcolor="{p["accent"]}" '
            f'{EDGE_ATTRS}];'
        )

    lines.append("}")
    return "\n".join(lines)


def build_module_tree_dot(spec: dict, theme: str = "professional") -> str:
    """Generate dot source for a module / component tree diagram.

    Uses rankdir=LR so that sibling-heavy trees grow rightward instead of
    creating impossibly wide horizontal ranks (12 grandchildren in one row
    becomes 12 grandchildren in one vertical column).

    spec.modules: [{"id": "...", "label": "...", "children": [...], "color": "primary|accent|success"}, ...]
    spec.root: "root_module_id"
    """
    p = palette(theme)
    direction = spec.get("direction", "LR")

    color_map = {
        "primary": (p["primary"], p["primary_light"]),
        "accent":  (p["accent"], p["accent_light"]),
        "success": (p["success"], p["success_light"]),
        "danger":  (p["danger"], p["danger_light"]),
        "neutral": (p["neutral"], p["neutral_light"]),
    }

    lines = [
        "digraph ModuleTree {",
        f"  rankdir={direction};",
        f"  newrank=true;",
        f"  nodesep=0.4;",
        f"  ranksep=0.5;",
        f"  {get_size_attrs(spec, 'module_tree')};",
        f"  {GRAPH_ATTRS}",
        "",
    ]

    # Flatten the tree into node + edge list
    node_counter = [0]
    node_map = {}

    def process_module(mod, parent_id=None):
        mid = mod.get("id", f"node_{node_counter[0]}")
        node_counter[0] += 1
        mlabel = dot_escape(mod.get("label", mid))
        mcolor = color_map.get(mod.get("color", "primary"),
                                color_map["primary"])
        border, fill = mcolor

        node_map[mid] = True
        lines.append(
            f'  {mid} [shape=box style="filled,rounded" '
            f'fillcolor="{fill}" color="{border}" '
            f'fontcolor="{p["text"]}" {NODE_BASE} '
            f'label="{mlabel}"];'
        )

        if parent_id:
            lines.append(f'  {parent_id} -> {mid} [{EDGE_ATTRS}];')

        for child in mod.get("children", []):
            process_module(child, mid)

    root_mod = spec.get("root")
    if root_mod and isinstance(root_mod, dict):
        process_module(root_mod)
    elif isinstance(root_mod, str):
        # Find the module by id in the flat list
        for mod in spec.get("modules", []):
            if mod.get("id") == root_mod:
                process_module(mod)
                break
        else:
            # Process all top-level modules
            for mod in spec.get("modules", []):
                process_module(mod)
    else:
        for mod in spec.get("modules", []):
            process_module(mod)

    lines.append("}")
    return "\n".join(lines)


def build_timeline_dot(spec: dict, theme: str = "professional") -> str:
    """Generate dot source for a process timeline / sequence diagram.

    spec.phases: [{"id": "...", "label": "...", "time": "...", "color": "primary|accent|success"}, ...]
    spec.connections: [{"from": "id", "to": "id", "label": "..."}, ...]
    """
    p = palette(theme)
    direction = spec.get("direction", "TB")

    color_map = {
        "primary": (p["primary"], p["primary_light"]),
        "accent":  (p["accent"], p["accent_light"]),
        "success": (p["success"], p["success_light"]),
        "danger":  (p["danger"], p["danger_light"]),
        "neutral": (p["neutral"], p["neutral_light"]),
    }

    lines = [
        "digraph Timeline {",
        f"  rankdir={direction};",
        f"  newrank=true;",
        f"  {GRAPH_ATTRS}",
        f"  nodesep=0.4; ranksep=0.6;",
        f"  {get_size_attrs(spec, 'timeline')};",
        "",
    ]

    for phase in spec.get("phases", []):
        pid = phase["id"]
        plabel = dot_escape(phase.get("label", pid))
        ptime = dot_escape(phase.get("time", ""))
        pcolor = color_map.get(phase.get("color", "primary"),
                                color_map["primary"])
        border, fill = pcolor
        display_label = f"{plabel}\\n({ptime})" if ptime else plabel

        shape = "box"
        if phase.get("shape") == "start" or phase.get("shape") == "end":
            shape = "oval"

        lines.append(
            f'  {pid} [shape={shape} style="filled,rounded" '
            f'fillcolor="{fill}" color="{border}" '
            f'fontcolor="{p["text"]}" {NODE_BASE} '
            f'label="{display_label}"];'
        )

    lines.append("")
    lines.append("  /* --- connections --- */")
    for conn in spec.get("connections", []):
        src = conn["from"]
        dst = conn["to"]
        elabel = dot_escape(conn.get("label", ""))
        if elabel:
            lines.append(f'  {src} -> {dst} [label="{elabel}" {EDGE_ATTRS}];')
        else:
            lines.append(f'  {src} -> {dst} [{EDGE_ATTRS}];')

    lines.append("}")
    return "\n".join(lines)


# ── Builder dispatch ───────────────────────────────────────────

BUILDERS = {
    "flowchart":     build_flowchart_dot,
    "architecture":  build_architecture_dot,
    "er_diagram":    build_er_diagram_dot,
    "module_tree":   build_module_tree_dot,
    "timeline":      build_timeline_dot,
}


# ── Rendering ──────────────────────────────────────────────────

def render_dot(dot_source: str, output_path: str) -> bool:
    """Render dot source to PNG via the `dot` binary."""
    if not DOT_AVAILABLE:
        print(f"[error] Graphviz `dot` binary not found. Install Graphviz first.")
        print(f"  Windows: choco install graphviz  or  download from https://graphviz.org/download/")
        return False

    try:
        proc = subprocess.run(
            [DOT_BIN, "-Tpng", f"-Gdpi=200", "-o", output_path],
            input=dot_source,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"[error] dot failed: {proc.stderr[:500]}")
            return False
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return True
        return False
    except FileNotFoundError:
        print(f"[error] dot binary not found at {DOT_BIN}")
        return False
    except subprocess.TimeoutExpired:
        print("[error] dot rendering timed out (30s)")
        return False


# ── Main ───────────────────────────────────────────────────────

def generate_figure(job: dict, theme: str = "professional") -> str | None:
    """Process a single diagram job. Returns output path or None."""
    job_id = job["id"]
    job_type = job.get("type", "flowchart")
    job_spec = job.get("spec", {})
    job_theme = job.get("theme", theme)

    builder = BUILDERS.get(job_type)
    if builder is None:
        print(f"[warn] Unknown diagram type '{job_type}' for {job_id}. "
              f"Supported: {list(BUILDERS.keys())}")
        return None

    dot_source = builder(job_spec, job_theme)
    output_path = os.path.join(FIG_DIR, f"{job_id}.png")

    # Write .dot for debugging
    dot_path = os.path.join(FIG_DIR, f"{job_id}.dot")
    with open(dot_path, "w", encoding="utf-8") as f:
        f.write(dot_source)

    success = render_dot(dot_source, output_path)
    if success:
        size = os.path.getsize(output_path)
        print(f"[ok] {job_id} -> {output_path} ({size} bytes)")
        return output_path
    else:
        # If Graphviz not available, save .dot for manual rendering
        print(f"[warn] {job_id}: PNG not rendered (Graphviz missing). "
              f".dot file saved at {dot_path}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate academic diagrams from JSON specs via Graphviz.")
    parser.add_argument("--spec", required=True,
                        help="Path to figures-spec.json")
    parser.add_argument("--job", default=None,
                        help="Render only a specific job by id")
    parser.add_argument("--theme", default="professional",
                        choices=["professional", "clean"],
                        help="Color theme")
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        all_jobs = json.load(f)

    if isinstance(all_jobs, dict):
        # Support both {"figures": [...]} and direct [...]
        all_jobs = all_jobs.get("figures", [all_jobs])

    if not isinstance(all_jobs, list):
        print("[error] figures-spec.json must be a list or {figures: [...]}")
        sys.exit(1)

    if args.job:
        all_jobs = [j for j in all_jobs if j.get("id") == args.job]
        if not all_jobs:
            print(f"[error] No job found with id '{args.job}'")
            sys.exit(1)

    # Update manifest
    manifest_jobs = []
    for job in all_jobs:
        out = generate_figure(job, args.theme)
        if out:
            relative = f"assets/figures/{job['id']}.png"
            manifest_jobs.append({
                "id": job["id"],
                "caption": job.get("caption", ""),
                "section_ref": job.get("section_ref", ""),
                "file": relative,
                "size_bytes": os.path.getsize(out),
            })

    if manifest_jobs:
        from assets_generate_figures import update_manifest
        mf = update_manifest(manifest_jobs, root=ROOT)
        print(f"[ok] manifest updated: {mf}")

    if not DOT_AVAILABLE:
        print("\n[info] Graphviz `dot` not found. .dot source files have been saved.")
        print("  Install Graphviz, then re-run this script to render PNGs.")
        print("  Windows: choco install graphviz")
        print("  Or download: https://graphviz.org/download/")


if __name__ == "__main__":
    main()
