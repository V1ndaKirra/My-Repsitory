# -*- coding: utf-8 -*-
"""从 figures-spec.json 生成可编辑的 .drawio 文件。"""
from __future__ import annotations

import json
import math
import os
import uuid
import xml.etree.ElementTree as ET

from thesis_schema import (
    load_thesis_json,
    merge_required_user_actions,
    save_thesis_json,
    update_collaboration_state,
)


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))
CONFIG_PATH = os.path.join(ROOT, "project", "figures-spec.json")
OUT_DIR = os.path.join(ROOT, "assets", "figures")
THESIS_PATH = os.path.join(ROOT, "thesis.json")
os.makedirs(OUT_DIR, exist_ok=True)

SUPPORTED_TYPES = {
    "architecture",
    "er_diagram",
    "module_tree",
    "deployment",
    "component",
    "use_case",
}

COLOR_MAP = {
    "primary": ("#dae8fc", "#6c8ebf"),
    "accent": ("#ffe6cc", "#d79b00"),
    "success": ("#d5e8d4", "#82b366"),
    "danger": ("#f8cecc", "#b85450"),
    "neutral": ("#f5f5f5", "#666666"),
}


class DrawioFile:
    def __init__(self, page_name: str):
        self.mxfile = ET.Element("mxfile", host="app.diagrams.net", version="24.7.17")
        self.diagram = ET.SubElement(self.mxfile, "diagram", id=uuid.uuid4().hex[:12], name=page_name)
        self.model = ET.SubElement(
            self.diagram,
            "mxGraphModel",
            dx="1200",
            dy="800",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth="1654",
            pageHeight="1169",
            math="0",
            shadow="0",
        )
        self.root = ET.SubElement(self.model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self._next_id = 2

    def next_id(self) -> str:
        value = str(self._next_id)
        self._next_id += 1
        return value

    def add_vertex(self, value: str, x: float, y: float, w: float, h: float, style: str) -> str:
        cell_id = self.next_id()
        cell = ET.SubElement(
            self.root,
            "mxCell",
            id=cell_id,
            value=value,
            style=style,
            vertex="1",
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), as_="geometry")
        return cell_id

    def add_edge(self, source: str, target: str, value: str = "", style: str | None = None) -> str:
        cell_id = self.next_id()
        style_value = style or (
            "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
            "jettySize=auto;html=1;endArrow=block;endFill=1;"
            "strokeColor=#666666;fontSize=11;"
        )
        cell = ET.SubElement(
            self.root,
            "mxCell",
            id=cell_id,
            value=value,
            style=style_value,
            edge="1",
            parent="1",
            source=source,
            target=target,
        )
        ET.SubElement(cell, "mxGeometry", relative="1", as_="geometry")
        return cell_id

    def write(self, path: str):
        self._fix_as_attribute(self.mxfile)
        tree = ET.ElementTree(self.mxfile)
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def _fix_as_attribute(self, element: ET.Element):
        if "as_" in element.attrib:
            element.attrib["as"] = element.attrib.pop("as_")
        for child in element:
            self._fix_as_attribute(child)


def color_pair(color_name: str | None) -> tuple[str, str]:
    return COLOR_MAP.get(color_name or "neutral", COLOR_MAP["neutral"])


def base_vertex_style(fill: str, stroke: str, rounded: bool = True) -> str:
    rounded_flag = "1" if rounded else "0"
    return (
        f"rounded={rounded_flag};whiteSpace=wrap;html=1;fillColor={fill};"
        f"strokeColor={stroke};fontSize=12;align=center;verticalAlign=middle;"
    )


def html_label(title: str, lines: list[str]) -> str:
    if not lines:
        return f"<b>{title}</b>"
    body = "<br/>".join(lines)
    return f"<b>{title}</b><hr/>{body}"


def build_architecture(doc: DrawioFile, job: dict):
    spec = job.get("spec", {})
    direction = spec.get("direction", "TB")
    cell_map: dict[str, str] = {}

    if direction == "LR":
        x = 40
        for layer in spec.get("layers", []):
            fill, stroke = color_pair(layer.get("color"))
            nodes = layer.get("nodes", [])
            layer_height = max(120, 70 + len(nodes) * 95)
            doc.add_vertex(
                f"<b>{layer.get('label', layer.get('id', 'Layer'))}</b>",
                x,
                30,
                220,
                50,
                base_vertex_style(fill, stroke, rounded=False),
            )
            node_y = 110
            for node in nodes:
                cell_map[node["id"]] = doc.add_vertex(
                    node.get("label", node["id"]).replace("\n", "<br/>"),
                    x,
                    node_y,
                    220,
                    70,
                    base_vertex_style(fill, stroke),
                )
                node_y += 95
            x += 280
    else:
        y = 30
        for layer in spec.get("layers", []):
            fill, stroke = color_pair(layer.get("color"))
            nodes = layer.get("nodes", [])
            doc.add_vertex(
                f"<b>{layer.get('label', layer.get('id', 'Layer'))}</b>",
                40,
                y,
                150,
                42,
                base_vertex_style(fill, stroke, rounded=False),
            )
            x = 220
            for node in nodes:
                cell_map[node["id"]] = doc.add_vertex(
                    node.get("label", node["id"]).replace("\n", "<br/>"),
                    x,
                    y - 8,
                    210,
                    72,
                    base_vertex_style(fill, stroke),
                )
                x += 240
            y += 110

    for conn in spec.get("connections", []):
        src = cell_map.get(conn.get("from"))
        dst = cell_map.get(conn.get("to"))
        if src and dst:
            doc.add_edge(src, dst, conn.get("label", ""))


def build_er_diagram(doc: DrawioFile, job: dict):
    spec = job.get("spec", {})
    entities = spec.get("entities", [])
    if not entities:
        return

    cols = 2 if len(entities) <= 4 else 3
    positions: dict[str, str] = {}

    for idx, entity in enumerate(entities):
        col = idx % cols
        row = idx // cols
        x = 40 + col * 280
        y = 40 + row * 240
        fields = []
        for field in entity.get("fields", []):
            prefix = ""
            if field.get("pk"):
                prefix = "[PK] "
            elif field.get("fk"):
                prefix = "[FK] "
            fields.append(prefix + str(field.get("name", "")))
        height = max(120, 70 + len(fields) * 22)
        positions[entity["id"]] = doc.add_vertex(
            html_label(entity.get("name", entity["id"]), fields),
            x,
            y,
            220,
            height,
            base_vertex_style("#ffffff", "#6c8ebf", rounded=False),
        )

    for rel in spec.get("relationships", []):
        src = positions.get(rel.get("from"))
        dst = positions.get(rel.get("to"))
        if not src or not dst:
            continue
        card_a = rel.get("card_a", "")
        card_b = rel.get("card_b", "")
        label = str(rel.get("label", "")).strip()
        parts = [p for p in [f"{card_a}:{card_b}" if card_a or card_b else "", label] if p]
        doc.add_edge(src, dst, "<br/>".join(parts))


def count_leaves(node: dict) -> int:
    children = node.get("children", [])
    if not children:
        return 1
    return sum(count_leaves(child) for child in children)


def place_tree(
    doc: DrawioFile,
    node: dict,
    depth: int,
    left_leaf_index: int,
    cell_map: dict[str, str],
    parent_id: str | None = None,
):
    leaf_count = count_leaves(node)
    x = 60 + left_leaf_index * 210 + (leaf_count - 1) * 105
    y = 50 + depth * 120
    fill, stroke = color_pair(node.get("color"))
    cell_id = doc.add_vertex(
        node.get("label", node.get("id", "")),
        x,
        y,
        160,
        60,
        base_vertex_style(fill, stroke),
    )
    cell_map[node.get("id", cell_id)] = cell_id
    if parent_id:
        doc.add_edge(parent_id, cell_id)

    next_leaf = left_leaf_index
    for child in node.get("children", []):
        child_leaves = count_leaves(child)
        place_tree(doc, child, depth + 1, next_leaf, cell_map, cell_id)
        next_leaf += child_leaves


def build_module_tree(doc: DrawioFile, job: dict):
    spec = job.get("spec", {})
    root = spec.get("root")
    if not isinstance(root, dict):
        return
    place_tree(doc, root, 0, 0, {})


def build_generic_network(doc: DrawioFile, job: dict):
    spec = job.get("spec", {})
    nodes = spec.get("nodes", []) or spec.get("components", [])
    links = spec.get("connections", []) or spec.get("edges", [])
    if not nodes:
        return

    cols = max(2, math.ceil(math.sqrt(len(nodes))))
    cell_map: dict[str, str] = {}
    for idx, node in enumerate(nodes):
        col = idx % cols
        row = idx // cols
        x = 60 + col * 250
        y = 60 + row * 140
        fill, stroke = color_pair(node.get("color"))
        cell_map[node["id"]] = doc.add_vertex(
            node.get("label", node["id"]).replace("\n", "<br/>"),
            x,
            y,
            180,
            70,
            base_vertex_style(fill, stroke),
        )
    for edge in links:
        src = cell_map.get(edge.get("from"))
        dst = cell_map.get(edge.get("to"))
        if src and dst:
            doc.add_edge(src, dst, edge.get("label", ""))


def build_use_case(doc: DrawioFile, job: dict):
    spec = job.get("spec", {})
    actors = spec.get("actors", [])
    use_cases = spec.get("use_cases", [])
    if not actors or not use_cases:
        return

    actor_map: dict[str, str] = {}
    case_map: dict[str, str] = {}

    for idx, actor in enumerate(actors):
        actor_map[actor["id"]] = doc.add_vertex(
            actor.get("label", actor["id"]),
            40,
            60 + idx * 140,
            110,
            60,
            "shape=umlActor;html=1;fontSize=12;",
        )

    for idx, item in enumerate(use_cases):
        case_map[item["id"]] = doc.add_vertex(
            item.get("label", item["id"]),
            260,
            40 + idx * 110,
            180,
            70,
            "ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;",
        )

    for conn in spec.get("connections", []):
        src = actor_map.get(conn.get("from")) or case_map.get(conn.get("from"))
        dst = case_map.get(conn.get("to")) or actor_map.get(conn.get("to"))
        if src and dst:
            doc.add_edge(src, dst, conn.get("label", ""), "endArrow=none;html=1;strokeColor=#666666;fontSize=11;")


BUILDERS = {
    "architecture": build_architecture,
    "er_diagram": build_er_diagram,
    "module_tree": build_module_tree,
    "deployment": build_generic_network,
    "component": build_generic_network,
    "use_case": build_use_case,
}


def load_jobs(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("figures", data)
    if not isinstance(jobs, list):
        raise SystemExit("[error] figures-spec.json 顶层必须是 figures 列表。")
    return jobs


def generate_drawio(job: dict) -> str | None:
    builder = BUILDERS.get(job.get("type"))
    if not builder:
        return None
    doc = DrawioFile(job.get("caption", job.get("id", "Diagram")))
    builder(doc, job)
    out_path = os.path.join(OUT_DIR, f"{job['id']}.drawio")
    doc.write(out_path)
    return out_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate editable draw.io diagrams from figures-spec.json."
    )
    parser.add_argument("--spec", default=CONFIG_PATH, help="figures-spec.json 路径")
    parser.add_argument("--job", default=None, help="只生成单个图 id")
    parser.add_argument("--type", default=None, help="只生成某个类型")
    args = parser.parse_args()

    if not os.path.exists(args.spec):
        print(f"[info] figures-spec.json not found: {args.spec}")
        return

    jobs = load_jobs(args.spec)
    selected = []
    for job in jobs:
        job_type = job.get("type")
        if job_type not in SUPPORTED_TYPES:
            continue
        if args.job and job.get("id") != args.job:
            continue
        if args.type and job_type != args.type:
            continue
        selected.append(job)

    if not selected:
        print("[info] no draw.io-eligible figures found")
        return

    print(f"[info] generating {len(selected)} draw.io file(s)")
    generated_paths = []
    for job in selected:
        out_path = generate_drawio(job)
        if out_path:
            generated_paths.append(out_path)
            print(f"[ok] {job['id']} -> {out_path}")

    if generated_paths and os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        actions = merge_required_user_actions(
            thesis.get("collaboration", {}).get("required_user_actions", []),
            [
                {
                    "kind": "review-drawio",
                    "title": "检查 draw.io 图",
                    "why": "draw.io 源文件已经生成，需要用户确认元素命名、关系和布局都来自真实项目。",
                    "expected_input": ", ".join(
                        os.path.relpath(path, ROOT).replace("\\", "/") for path in generated_paths[:5]
                    ),
                    "done_when": "用户确认 draw.io 图无误，必要时导出 PNG/JPG 再继续后续排版。",
                }
            ],
        )
        update_collaboration_state(
            thesis,
            current_gate="phase-5-drawio-generated",
            waiting_for_user=True,
            required_user_actions=actions,
            last_agent_summary="已生成 draw.io 图文件，请先让用户检查并确认是否需要继续导出 PNG/JPG。",
        )
        save_thesis_json(THESIS_PATH, thesis)


if __name__ == "__main__":
    main()
