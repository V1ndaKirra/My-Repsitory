# -*- coding: utf-8 -*-
"""Build non-destructive draft sidecars from chapter kits.

Outputs guide files next to existing drafts, for example:
  - drafts/04-system-design.guide.md
  - drafts/05-implementation.guide.md
  - drafts/06-system-test.guide.md
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
THESIS_PATH = os.path.join(ROOT, "thesis.json")
KIT_INDEX_PATH = os.path.join(ROOT, "project", "chapter-kits", "index.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def chapter_map(thesis: dict) -> dict[str, dict]:
    return {
        item.get("id"): item
        for item in thesis.get("outline", [])
        if item.get("id")
    }


def guide_path_for_draft(draft_path: str) -> str:
    base, ext = os.path.splitext(draft_path)
    return f"{base}.guide{ext or '.md'}"


def collect_paths(items: list[dict], limit: int = 10) -> list[str]:
    paths = []
    for item in items:
        path = item.get("path")
        if path and path not in paths:
            paths.append(path)
        if len(paths) >= limit:
            break
    return paths


def build_guide_lines(chapter: dict, kit: dict) -> list[str]:
    lines = [
        f"# {kit['chapter_id']} 写作侧边提示",
        "",
        f"- 生成时间：{now_iso()}",
        f"- 对应草稿：`{chapter.get('draft_path', '')}`",
        f"- 本章目标：{kit.get('goal', '')}",
        "",
        "## 先写什么",
        "",
    ]
    for item in kit.get("write_order", [])[:3]:
        lines.append(f"- {item}")

    lines.extend(["", "## 必答问题", ""])
    for item in kit.get("must_answer", [])[:5]:
        lines.append(f"- {item}")

    if kit.get("module_packets"):
        lines.extend(["", "## 本章优先写的模块", ""])
        for module in kit["module_packets"][:4]:
            lines.append(f"### {module.get('module')}")
            lines.append("")
            lines.append(f"- 写作提示：{module.get('writing_prompt', '')}")
            for path_item in module.get("suggested_paths", [])[:3]:
                lines.append(f"- path: `{path_item.get('path')}`")
            for method in module.get("service_methods", [])[:3]:
                lines.append(f"- 服务方法：`{method}`")
            for api in module.get("apis", [])[:3]:
                lines.append(f"- API：`{api}`")
            for shot in module.get("screenshot_suggestions", [])[:1]:
                lines.append(f"- 截图：`{shot.get('id')}` {shot.get('caption')}")
                if shot.get("proof_note"):
                    lines.append(f"  证明点：{shot.get('proof_note')}")
                lines.append(f"  示例句：{shot.get('example_sentence')}")
            lines.append("")

    evidence_paths = collect_paths(kit.get("evidence_paths", []), limit=10)
    if evidence_paths:
        lines.extend(["", "## 可直接引用的证据路径", ""])
        for path in evidence_paths:
            lines.append(f"- `{path}`")

    if kit.get("tech_choice_prompts"):
        lines.extend(["", "## 技术选型可直接回答", ""])
        for item in kit["tech_choice_prompts"][:6]:
            lines.append(f"- {item.get('topic')}: {item.get('prompt')}")

    if kit.get("challenge_prompts"):
        lines.extend(["", "## 问题与修复怎么写", ""])
        for item in kit["challenge_prompts"][:5]:
            title = item.get("title") or "问题"
            prompt = item.get("prompt") or ""
            lines.append(f"- {title}: {prompt}")
            for key, label in (
                ("symptom_prompt", "现象"),
                ("diagnosis_prompt", "排查"),
                ("fix_prompt", "修复"),
                ("result_prompt", "结果"),
            ):
                if item.get(key):
                    lines.append(f"  {label}: {item[key]}")
            if item.get("defense_angle"):
                lines.append(f"  答辩价值: {item.get('defense_angle')}")
            for observed in item.get("observed_from", [])[:3]:
                lines.append(f"  observed_from: `{observed}`")

    if kit.get("challenge_sections"):
        lines.extend(["", "## 可直接落文的小节结构", ""])
        for item in kit["challenge_sections"][:4]:
            lines.append(f"### {item.get('heading')}")
            lines.append("")
            if item.get("summary"):
                lines.append(f"- 小节概述：{item.get('summary')}")
            for key, label in (
                ("symptom_prompt", "现象"),
                ("diagnosis_prompt", "排查"),
                ("fix_prompt", "修复"),
                ("result_prompt", "结果"),
            ):
                if item.get(key):
                    lines.append(f"- {label}：{item.get(key)}")
            if item.get("defense_angle"):
                lines.append(f"- 答辩价值：{item.get('defense_angle')}")
            for observed in item.get("observed_from", [])[:3]:
                lines.append(f"- observed_from: `{observed}`")
            lines.append("")

    screenshot_items = kit.get("screenshot_suggestions") or kit.get("general_screenshot_suggestions") or []
    if screenshot_items:
        lines.extend(["", "## 截图自然引用", ""])
        for item in screenshot_items[:4]:
            lines.append(f"- `{item.get('id')}` {item.get('caption')}")
            if item.get("proof_note"):
                lines.append(f"  证明点：{item.get('proof_note')}")
            lines.append(f"  示例句：{item.get('example_sentence')}")

    lines.extend(["", "## 使用方式", "", "- 先看这个 guide，再回到正式草稿落文。", "- 写完后删除对应段落里的 TODO，并补上 path、截图和问题复盘。"])
    return lines


def main():
    parser = argparse.ArgumentParser(
        description="Build non-destructive sidecar guides next to draft markdown files."
    )
    parser.parse_args()

    if not os.path.exists(THESIS_PATH):
        raise SystemExit(f"[error] thesis not found: {THESIS_PATH}")
    if not os.path.exists(KIT_INDEX_PATH):
        raise SystemExit(f"[error] chapter kit index not found: {KIT_INDEX_PATH}")

    thesis = load_json(THESIS_PATH)
    kit_index = load_json(KIT_INDEX_PATH)
    chapters = chapter_map(thesis)

    written = []
    for kit in kit_index.get("kits", []):
        chapter = chapters.get(kit.get("chapter_id"))
        if not chapter or not chapter.get("draft_path"):
            continue
        guide_rel = guide_path_for_draft(chapter["draft_path"])
        guide_abs = os.path.join(ROOT, guide_rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(guide_abs), exist_ok=True)
        lines = build_guide_lines(chapter, kit)
        with open(guide_abs, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")
        written.append(guide_rel.replace("\\", "/"))

    if not written:
        raise SystemExit("[error] no sidecar guides were written")

    print(f"[ok] sidecar guides written: {len(written)}")
    for path in written:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
