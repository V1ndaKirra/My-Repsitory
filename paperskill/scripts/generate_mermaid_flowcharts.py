# -*- coding: utf-8 -*-
"""从 figures-spec.json 生成 Mermaid 流程图代码。"""
from __future__ import annotations

import json
import os
import re
import sys

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

SUPPORTED_TYPES = {"flowchart", "timeline"}


def mermaid_escape(text: str) -> str:
    value = str(text or "").replace("\r", "")
    value = value.replace('"', "&quot;")
    value = value.replace("\n", "<br/>")
    return value


def mermaid_node(node_id: str, label: str, shape: str) -> str:
    safe = mermaid_escape(label)
    mapping = {
        "start": f'{node_id}(["{safe}"])',
        "end": f'{node_id}(["{safe}"])',
        "process": f'{node_id}["{safe}"]',
        "decision": f'{node_id}{{"{safe}"}}',
        "data": f'{node_id}[/"{safe}"/]',
        "manual": f'{node_id}[["{safe}"]]',
    }
    return mapping.get(shape or "process", mapping["process"])


def build_flowchart(job: dict) -> str:
    spec = job.get("spec", {})
    direction = spec.get("direction", "TB")
    lines = [f"flowchart {direction}"]

    seen = set()
    for node in spec.get("nodes", []):
        node_id = str(node.get("id", "")).strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        lines.append(f"    {mermaid_node(node_id, node.get('label', node_id), node.get('shape', 'process'))}")

    for edge in spec.get("edges", []):
        src = str(edge.get("from", "")).strip()
        dst = str(edge.get("to", "")).strip()
        if not src or not dst:
            continue
        label = str(edge.get("label", "")).strip()
        if label:
            lines.append(f'    {src} -->|"{mermaid_escape(label)}"| {dst}')
        else:
            lines.append(f"    {src} --> {dst}")

    return "\n".join(lines) + "\n"


def build_timeline(job: dict) -> str:
    spec = job.get("spec", {})
    direction = spec.get("direction", "TB")
    steps = spec.get("steps", [])
    lines = [f"flowchart {direction}"]

    prev_id = None
    for idx, step in enumerate(steps, 1):
        node_id = str(step.get("id") or f"step_{idx}").strip()
        label = step.get("label", node_id)
        lines.append(f'    {node_id}["{mermaid_escape(label)}"]')
        if prev_id:
            edge_label = str(step.get("edge_label", "")).strip()
            if edge_label:
                lines.append(f'    {prev_id} -->|"{mermaid_escape(edge_label)}"| {node_id}')
            else:
                lines.append(f"    {prev_id} --> {node_id}")
        prev_id = node_id

    return "\n".join(lines) + "\n"


BUILDERS = {
    "flowchart": build_flowchart,
    "timeline": build_timeline,
}


def load_jobs(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("figures", data)
    if not isinstance(jobs, list):
        raise SystemExit("[error] figures-spec.json 顶层必须是 figures 列表。")
    return jobs


def write_mermaid(job: dict) -> str | None:
    job_type = job.get("type")
    builder = BUILDERS.get(job_type)
    if not builder:
        return None
    output = builder(job)
    out_path = os.path.join(OUT_DIR, f"{job['id']}.mmd")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)
    return out_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Mermaid flowchart code from figures-spec.json."
    )
    parser.add_argument("--spec", default=CONFIG_PATH, help="figures-spec.json 路径")
    parser.add_argument("--job", default=None, help="只生成单个图 id")
    parser.add_argument("--type", default=None, help="只生成某个类型，默认 flowchart/timeline")
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
        print("[info] no Mermaid-eligible figures found")
        return

    print(f"[info] generating {len(selected)} Mermaid file(s)")
    generated_paths = []
    for job in selected:
        out_path = write_mermaid(job)
        if out_path:
            generated_paths.append(out_path)
            print(f"[ok] {job['id']} -> {out_path}")

    if generated_paths and os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        actions = merge_required_user_actions(
            thesis.get("collaboration", {}).get("required_user_actions", []),
            [
                {
                    "kind": "review-mermaid",
                    "title": "检查 Mermaid 流程图",
                    "why": "Mermaid 代码已经生成，需要用户复制到 draw.io、调整节点后再回传路径。",
                    "expected_input": ", ".join(
                        os.path.relpath(path, ROOT).replace("\\", "/") for path in generated_paths[:5]
                    ),
                    "done_when": "用户确认 Mermaid 内容准确，并将 draw.io 产物保存回工作区。",
                }
            ],
        )
        update_collaboration_state(
            thesis,
            current_gate="phase-5-mermaid-generated",
            waiting_for_user=True,
            required_user_actions=actions,
            last_agent_summary="已生成 Mermaid 流程图代码，请先让用户检查并回传 draw.io 产物路径。",
        )
        save_thesis_json(THESIS_PATH, thesis)


if __name__ == "__main__":
    main()
