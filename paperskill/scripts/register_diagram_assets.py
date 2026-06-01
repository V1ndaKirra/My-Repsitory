# -*- coding: utf-8 -*-
"""Register confirmed Mermaid / draw.io diagram assets into assets/manifest.json."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from thesis_schema import (
    load_thesis_json,
    merge_required_user_actions,
    remove_required_user_actions,
    save_thesis_json,
    update_collaboration_state,
)


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
FIGURES_DIR = os.path.join(ROOT, "assets", "figures")
MANIFEST_PATH = os.path.join(ROOT, "assets", "manifest.json")
THESIS_PATH = os.path.join(ROOT, "thesis.json")
SPEC_PATH = os.path.join(ROOT, "project", "figures-spec.json")
RENDER_EXTS = [".png", ".jpg", ".jpeg", ".bmp", ".gif"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_manifest() -> list[dict]:
    if not os.path.exists(MANIFEST_PATH):
        return []
    try:
        data = json.load(open(MANIFEST_PATH, "r", encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_jobs() -> dict[str, dict]:
    if not os.path.exists(SPEC_PATH):
        return {}
    data = json.load(open(SPEC_PATH, "r", encoding="utf-8"))
    jobs = data.get("figures", data)
    if not isinstance(jobs, list):
        return {}
    return {str(job.get("id")): job for job in jobs if job.get("id")}


def rel_to_root(path: str) -> str:
    rel = os.path.relpath(path, ROOT)
    if rel.startswith(".."):
        raise SystemExit(f"[error] file must stay inside workspace: {path}")
    return rel.replace("\\", "/")


def source_format_from_ext(ext: str) -> str:
    ext = ext.lower()
    if ext == ".mmd":
        return "mermaid-code"
    if ext == ".drawio":
        return "drawio-editable"
    return ext.lstrip(".") or "unknown"


def detect_render_file(source_path: str) -> str:
    stem, _ = os.path.splitext(source_path)
    candidates = [stem + ext for ext in RENDER_EXTS]
    rendered_dir = os.path.join(FIGURES_DIR, "rendered")
    base_name = os.path.basename(stem)
    candidates.extend([os.path.join(rendered_dir, base_name + ext) for ext in RENDER_EXTS])
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def gather_sources(args) -> list[str]:
    sources = []
    if args.file:
        for item in args.file:
            path = item if os.path.isabs(item) else os.path.join(ROOT, item.replace("/", os.sep))
            if not os.path.exists(path):
                raise SystemExit(f"[error] diagram source not found: {item}")
            sources.append(os.path.abspath(path))
        return sources

    if not os.path.exists(FIGURES_DIR):
        return []
    for name in sorted(os.listdir(FIGURES_DIR)):
        ext = os.path.splitext(name)[1].lower()
        if ext not in {".mmd", ".drawio"}:
            continue
        sources.append(os.path.join(FIGURES_DIR, name))
    return sources


def build_entry(source_path: str, jobs: dict[str, dict]) -> dict:
    source_path = os.path.abspath(source_path)
    asset_id = os.path.splitext(os.path.basename(source_path))[0]
    job = jobs.get(asset_id, {})
    render_path = detect_render_file(source_path)
    render_rel = rel_to_root(render_path) if render_path else ""
    source_rel = rel_to_root(source_path)
    return {
        "id": asset_id,
        "type": "figure",
        "caption": job.get("caption") or asset_id,
        "file": source_rel,
        "render_file": render_rel,
        "source_format": source_format_from_ext(os.path.splitext(source_path)[1]),
        "section_ref": job.get("section_ref") or "",
        "editor_confirmed": True,
        "ready_for_docx": bool(render_rel),
        "generated_at": now_iso(),
    }


def update_manifest(entries: list[dict]):
    existing = load_manifest()
    replace_ids = {entry["id"] for entry in entries}
    preserved = [item for item in existing if item.get("id") not in replace_ids]
    merged = preserved + entries
    json.dump(merged, open(MANIFEST_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def sync_thesis(entries: list[dict]):
    if not os.path.exists(THESIS_PATH):
        return
    thesis = load_thesis_json(THESIS_PATH)
    thesis["user_inputs"]["diagram_dir"] = "assets/figures"
    thesis["user_inputs"]["diagram_dir_confirmed"] = True

    remaining_actions = remove_required_user_actions(
        thesis.get("collaboration", {}).get("required_user_actions", []),
        "review-mermaid",
        "review-drawio",
        "export-diagram-images",
    )

    pending_export = [entry["id"] for entry in entries if not entry.get("ready_for_docx")]
    if pending_export:
        remaining_actions = merge_required_user_actions(
            remaining_actions,
            [
                {
                    "kind": "export-diagram-images",
                    "title": "导出图表图片",
                    "why": "Mermaid / draw.io 源文件已经确认，但还没有导出成 docx 可插入的图片。",
                    "expected_input": ", ".join(f"{asset_id}.png" for asset_id in pending_export),
                    "done_when": "对应 PNG/JPG 导出文件已放回 assets/figures 或 assets/figures/rendered。",
                }
            ],
        )

    summary = (
        "已登记用户确认过的 Mermaid / draw.io 图表资产到 assets/manifest.json。"
        "如仍缺 PNG/JPG 导出图，preflight 会继续提示补导出。"
    )
    update_collaboration_state(
        thesis,
        current_gate="phase-5-diagram-assets-registered",
        waiting_for_user=bool(remaining_actions),
        required_user_actions=remaining_actions,
        last_agent_summary=summary,
    )
    save_thesis_json(THESIS_PATH, thesis)


def main():
    parser = argparse.ArgumentParser(
        description="Register confirmed Mermaid / draw.io assets into assets/manifest.json."
    )
    parser.add_argument(
        "--file",
        action="append",
        help="Source file path relative to workspace or absolute path. Can be used multiple times.",
    )
    args = parser.parse_args()

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    jobs = load_jobs()
    sources = gather_sources(args)
    if not sources:
        print("[info] no Mermaid / draw.io sources found")
        return

    entries = [build_entry(path, jobs) for path in sources]
    update_manifest(entries)
    sync_thesis(entries)

    ready_count = 0
    for entry in entries:
        state = "ready" if entry.get("ready_for_docx") else "pending-export"
        if entry.get("ready_for_docx"):
            ready_count += 1
        print(f"[ok] {entry['id']} -> {entry['file']} ({state})")
    print(f"[ok] manifest updated: {MANIFEST_PATH} ({len(entries)} diagram asset(s), {ready_count} docx-ready)")


if __name__ == "__main__":
    main()
