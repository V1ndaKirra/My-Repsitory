# -*- coding: utf-8 -*-
"""thesis.json schema helper.

提供最小向后兼容迁移能力：
- 自动补齐 context_bridge 缺失键
- 不覆盖用户已有值
"""
from __future__ import annotations

import copy
import json
import os


def default_context_bridge() -> dict:
    return {
        "last_session": None,
        "last_phase": "init",
        "last_chapter_completed": None,
        "next_action": "Phase 1: 项目理解（生成 project/profile.json）",
        "attention_flags": [],
        "chapter_briefs_ready": [],
        "lit_index_ready": False,
        "unresolved_issues": [],
    }


def default_user_inputs() -> dict:
    return {
        "repo_root": "",
        "repo_root_confirmed": False,
        "zh_pdf_dir": "",
        "zh_pdf_dir_confirmed": False,
        "screenshot_dir": "assets/screenshots",
        "screenshot_dir_confirmed": False,
        "diagram_dir": "assets/figures",
        "diagram_dir_confirmed": False,
    }


def default_collaboration() -> dict:
    return {
        "mode": "interactive-checkpoints",
        "current_gate": "phase-0-init",
        "waiting_for_user": False,
        "required_user_actions": [],
        "last_agent_summary": "",
    }


def normalize_required_user_actions(actions) -> list[dict]:
    normalized = []
    for idx, action in enumerate(actions or [], 1):
        if isinstance(action, str):
            text = action.strip()
            if text:
                normalized.append(
                    {
                        "kind": f"legacy-action-{idx}",
                        "title": text,
                        "done_when": "",
                    }
                )
            continue
        if not isinstance(action, dict):
            continue
        title = str(action.get("title") or action.get("kind") or "").strip()
        if not title:
            continue
        normalized.append(
            {
                "kind": str(action.get("kind") or f"action-{idx}").strip(),
                "title": title,
                "why": str(action.get("why") or "").strip(),
                "expected_input": str(action.get("expected_input") or "").strip(),
                "done_when": str(action.get("done_when") or "").strip(),
            }
        )
    return normalized


def merge_required_user_actions(*groups) -> list[dict]:
    merged = []
    seen = set()
    for group in groups:
        for action in normalize_required_user_actions(group):
            key = action.get("kind") or action.get("title")
            if key in seen:
                continue
            seen.add(key)
            merged.append(action)
    return merged


def remove_required_user_actions(actions, *kinds: str) -> list[dict]:
    blocked = {str(kind).strip() for kind in kinds if str(kind).strip()}
    return [
        action for action in normalize_required_user_actions(actions)
        if action.get("kind") not in blocked
    ]


def update_collaboration_state(
    thesis: dict,
    *,
    current_gate: str | None = None,
    waiting_for_user: bool | None = None,
    required_user_actions=None,
    last_agent_summary: str | None = None,
) -> dict:
    collaboration = thesis.setdefault("collaboration", {})
    if current_gate is not None:
        collaboration["current_gate"] = current_gate
    if waiting_for_user is not None:
        collaboration["waiting_for_user"] = waiting_for_user
    if required_user_actions is not None:
        collaboration["required_user_actions"] = normalize_required_user_actions(required_user_actions)
    if last_agent_summary is not None:
        collaboration["last_agent_summary"] = last_agent_summary
    return thesis


def migrate_thesis_schema(thesis: dict) -> tuple[dict, bool]:
    """补齐 thesis.json 中旧 schema 缺失的兼容字段。"""
    changed = False

    context_bridge = thesis.get("context_bridge")
    if not isinstance(context_bridge, dict):
        context_bridge = {}
        thesis["context_bridge"] = context_bridge
        changed = True

    for key, value in default_context_bridge().items():
        if key not in context_bridge:
            context_bridge[key] = copy.deepcopy(value)
            changed = True

    user_inputs = thesis.get("user_inputs")
    if not isinstance(user_inputs, dict):
        user_inputs = {}
        thesis["user_inputs"] = user_inputs
        changed = True

    for key, value in default_user_inputs().items():
        if key not in user_inputs:
            user_inputs[key] = copy.deepcopy(value)
            changed = True

    collaboration = thesis.get("collaboration")
    if not isinstance(collaboration, dict):
        collaboration = {}
        thesis["collaboration"] = collaboration
        changed = True

    for key, value in default_collaboration().items():
        if key not in collaboration:
            collaboration[key] = copy.deepcopy(value)
            changed = True

    return thesis, changed


def save_thesis_json(path: str, thesis: dict):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(thesis, f, ensure_ascii=False, indent=2)
    os.replace(path + ".tmp", path)


def load_thesis_json(path: str, persist_if_changed: bool = True) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        thesis = json.load(f)
    thesis, changed = migrate_thesis_schema(thesis)
    if changed and persist_if_changed:
        save_thesis_json(path, thesis)
    return thesis
