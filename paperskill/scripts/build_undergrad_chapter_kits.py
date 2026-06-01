# -*- coding: utf-8 -*-
"""Build chapter-level writing kits for undergrad defense-oriented drafting.

Outputs:
  - project/chapter-kits/index.json
  - project/chapter-kits/ch3-requirements.md
  - project/chapter-kits/ch4-system-design.md
  - project/chapter-kits/ch5-implementation.md
  - project/chapter-kits/ch6-test-and-debug.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone

from thesis_schema import (
    load_thesis_json,
    merge_required_user_actions,
    save_thesis_json,
    update_collaboration_state,
)


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
PROFILE_PATH = os.path.join(ROOT, "project", "profile.json")
PACK_PATH = os.path.join(ROOT, "project", "undergrad-evidence-pack.json")
MANIFEST_PATH = os.path.join(ROOT, "assets", "manifest.json")
OUT_DIR = os.path.join(ROOT, "project", "chapter-kits")
OUT_INDEX = os.path.join(OUT_DIR, "index.json")
THESIS_PATH = os.path.join(ROOT, "thesis.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(name)).strip("-").lower()
    return slug or "item"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def caption_subject(caption: str) -> str:
    cleaned = str(caption or "")
    for token in ("截图", "界面", "页面", "代码", "运行结果", "测试结果", "报错信息"):
        cleaned = cleaned.replace(token, "")
    return cleaned.strip() or "该功能"


def load_required_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        raise SystemExit(f"[error] profile not found: {PROFILE_PATH}")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evidence_lookup(profile: dict) -> dict[str, list[str]]:
    lookup = {}
    for item in profile.get("evidence_index", []):
        path = item.get("path")
        evidence = [e for e in item.get("evidence", []) if e]
        if path and evidence:
            lookup[path] = evidence
    return lookup


def collect_manual_screenshots(assets: list[dict]) -> list[dict]:
    return [
        a for a in assets
        if a.get("type") == "figure"
        and str(a.get("source_format", "")).lower() == "manual-screenshot"
    ]


def screenshot_usage_phase(asset: dict) -> str:
    hints = " ".join(
        [
            str(asset.get("caption", "")),
            str(asset.get("proof_note", "")),
            str(asset.get("section_ref", "")),
            str(asset.get("module_hint", "")),
            " ".join(asset.get("tags", []) if isinstance(asset.get("tags"), list) else [str(asset.get("tags", ""))]),
        ]
    )
    normalized = normalize_text(hints)
    if any(
        flag in normalized
        for flag in (
            "鎶ラ敊",
            "寮傚父",
            "閿欒",
            "澶辫触",
            "淇",
            "鎺掓煡",
            "鏃ュ織",
            "娴嬭瘯",
            "杩愯缁撴灉",
            "error",
            "debug",
            "log",
            "fix",
            "trace",
        )
    ):
        return "debugging"
    return "implementation"


def preferred_challenges(challenges: list[dict], limit: int = 6) -> list[dict]:
    focus_rank = {"core_business": 0, "implementation": 1, "supporting": 2}
    ordered = sorted(
        challenges,
        key=lambda item: (
            focus_rank.get(item.get("focus"), 9),
            -item.get("priority", 0),
            item.get("title", ""),
        ),
    )
    primary = [item for item in ordered if item.get("focus") in {"core_business", "implementation"}]
    fallback = [item for item in ordered if item.get("focus") not in {"core_business", "implementation"}]
    result = primary[:limit]
    if len(result) < limit:
        result.extend(fallback[: limit - len(result)])
    return result


def pick_matching_screenshots(
    shots: list[dict],
    keywords: list[str],
    fallback_section_prefix: str,
    limit: int = 3,
    usage_phase: str | None = None,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    scored = []
    exclude_ids = exclude_ids or set()
    for shot in shots:
        shot_id = shot.get("id")
        if shot_id and shot_id in exclude_ids:
            continue
        if usage_phase and screenshot_usage_phase(shot) != usage_phase:
            continue
        haystack = " ".join(
            [
                str(shot.get("caption", "")),
                str(shot.get("file", "")),
                str(shot.get("section_ref", "")),
                str(shot.get("module_hint", "")),
                str(shot.get("proof_note", "")),
                " ".join(shot.get("tags", []) if isinstance(shot.get("tags"), list) else [str(shot.get("tags", ""))]),
            ]
        )
        normalized = normalize_text(haystack)
        score = 0
        for keyword in keywords:
            if keyword and normalize_text(keyword) in normalized:
                score += 3
        section_ref = str(shot.get("section_ref", ""))
        if fallback_section_prefix and section_ref.startswith(fallback_section_prefix):
            score += 1
        if any(flag in normalized for flag in ("报错", "异常", "错误", "测试", "运行结果")):
            score += 1
        if score > 0:
            scored.append((score, shot))
    scored.sort(key=lambda item: (-item[0], item[1].get("id", "")))
    seen = set()
    result = []
    for _, shot in scored:
        shot_id = shot.get("id")
        if not shot_id or shot_id in seen:
            continue
        seen.add(shot_id)
        result.append(shot)
        if len(result) >= limit:
            break
    return result


def screenshot_example_sentence(asset: dict, chapter_theme: str) -> str:
    asset_id = asset.get("id", "shot-xx")
    caption = str(asset.get("caption", "实现截图"))
    proof_note = str(asset.get("proof_note", "")).strip()
    if proof_note:
        proof_note = proof_note.rstrip("。;；")
        return f"待用户补充 `{{{{fig:{asset_id}}}}}` 对应截图后，可在正文写成：如图所示，{proof_note}。"
    subject = caption_subject(caption)
    normalized = normalize_text(caption)
    if "代码" in normalized:
        return f"待用户补充 `{{{{fig:{asset_id}}}}}` 对应代码截图后，可在正文写成：如图所示，这里可以顺着说明 {subject} 的核心实现逻辑和关键判断条件。"
    if any(flag in normalized for flag in ("报错", "异常", "错误", "失败")):
        return f"待用户补充 `{{{{fig:{asset_id}}}}}` 对应报错或异常截图后，可在正文写成：如图所示，{subject} 在开发阶段出现过问题，后文继续交代排查过程和最终修复办法。"
    if any(flag in normalized for flag in ("测试", "运行结果", "结果")) or chapter_theme == "ch6":
        return f"待用户补充 `{{{{fig:{asset_id}}}}}` 对应运行结果或测试截图后，可在正文写成：如图所示，{subject} 的运行结果达到了预期，可作为测试或修复完成后的直接证据。"
    return f"待用户补充 `{{{{fig:{asset_id}}}}}` 对应截图后，可在正文写成：如图所示，{subject} 可用于证明本节提到的实现效果。"


def module_keywords(module: dict) -> list[str]:
    keywords = [module.get("name", "")]
    keywords.extend(module.get("key_classes", [])[:3])
    keywords.extend(module.get("entities", [])[:3])
    for api in module.get("apis", [])[:3]:
        keywords.append(api.split(" ", 1)[-1])
    return [k for k in keywords if k]


def top_modules(profile: dict, limit: int = 6) -> list[dict]:
    modules = profile.get("modules", [])
    return sorted(modules, key=lambda item: item.get("loc", 0), reverse=True)[:limit]


def build_ch6_sections(challenges: list[dict]) -> list[dict]:
    sections = []
    for idx, item in enumerate(challenges[:4], 1):
        sections.append(
            {
                "heading": f"6.2.{idx} {item.get('title')}",
                "summary": item.get("prompt"),
                "symptom_prompt": item.get("symptom_prompt"),
                "diagnosis_prompt": item.get("diagnosis_prompt"),
                "fix_prompt": item.get("fix_prompt"),
                "result_prompt": item.get("result_prompt"),
                "defense_angle": item.get("defense_angle"),
                "observed_from": item.get("observed_from", []),
            }
        )
    return sections


def related_frontend_pages(profile: dict, module: dict) -> list[dict]:
    module_key = slugify(module.get("name", ""))
    result = []
    for page in profile.get("frontend_pages", []):
        haystack = slugify(" ".join([page.get("name", ""), page.get("file", ""), page.get("route_hint", "")]))
        if module_key and module_key in haystack:
            result.append(page)
    return result[:4]


def merged_paths(primary: list[str], secondary: list[str], limit: int) -> list[str]:
    merged = []
    for path in primary + secondary:
        if path and path not in merged:
            merged.append(path)
        if len(merged) >= limit:
            break
    return merged


def chapter_actions(pack: dict, *kinds: str) -> list[dict]:
    actions = []
    for item in pack.get("required_user_actions", []):
        if item.get("kind") in kinds:
            actions.append(item)
    return actions


def chapter_diagrams(pack: dict, chapter_id: str) -> list[dict]:
    return [item for item in pack.get("diagram_tasks", []) if item.get("chapter") == chapter_id]


def chapter_brainstorm_tasks(pack: dict, chapter_id: str) -> list[dict]:
    return [item for item in pack.get("brainstorm_tasks", []) if item.get("chapter") == chapter_id]


def make_screenshot_payload(asset: dict, chapter_id: str) -> dict:
    return {
        "id": asset.get("id"),
        "caption": asset.get("caption"),
        "section_ref": asset.get("section_ref"),
        "proof_note": asset.get("proof_note"),
        "example_sentence": screenshot_example_sentence(asset, chapter_id),
    }


def build_ch3_kit(profile: dict, pack: dict, shots: list[dict], evidence_map: dict[str, list[str]]) -> dict:
    modules = top_modules(profile, limit=6)
    keywords = []
    for module in modules:
        keywords.extend(module_keywords(module))
    matched_shots = pick_matching_screenshots(shots, keywords or ["需求", "流程", "业务"], "3.", limit=3)
    evidence_paths = merged_paths(
        [
            item.get("path")
            for item in profile.get("evidence_index", [])
            if str(item.get("path", "")).startswith(("modules.", "frontend_pages.", "apis."))
        ][:12],
        pack.get("chapter_focus", {}).get("ch3", {}).get("recommended_paths", []),
        12,
    )
    return {
        "chapter_id": "ch3",
        "title": "需求分析",
        "goal": "把系统面向谁、要解决什么问题、核心业务怎么流转讲清楚，并提前规划后续要补的流程图和截图。",
        "write_order": [
            "先写项目的业务背景和目标用户，再落到系统边界和核心功能模块。",
            "接着用真实页面、接口或状态流转梳理 1 个核心业务流程，优先生成 Mermaid 流程图给用户检查。",
            "最后说明这些需求如何映射到后续系统设计和实现章节。",
        ],
        "must_answer": [
            "系统主要服务哪些角色，他们各自要完成什么任务？",
            "核心业务流程是怎样一步步发生的？",
            "这些需求如何落到后续模块、页面、接口或数据库设计上？",
        ],
        "evidence_paths": [{"path": path, "files": evidence_map.get(path, [])} for path in evidence_paths],
        "diagram_tasks": chapter_diagrams(pack, "ch3"),
        "brainstorm_tasks": chapter_brainstorm_tasks(pack, "ch3"),
        "required_user_actions": chapter_actions(pack, "confirm-repo-root", "review-mermaid", "review-drawio"),
        "screenshot_suggestions": [make_screenshot_payload(asset, "ch3") for asset in matched_shots],
        "defense_points": [
            "需求分析不要空写“提高效率”，要把角色、操作步骤和系统响应串起来。",
            "如果流程图还没回传到工作区，正文里先预留 [TODO: 插入需求/业务流程图]，不要假装图片已经存在。",
        ],
    }


def build_ch4_kit(profile: dict, pack: dict, shots: list[dict], evidence_map: dict[str, list[str]]) -> dict:
    tech_decisions = profile.get("tech_decisions", [])[:6]
    entities = profile.get("data_model", {}).get("entities", [])[:8]
    tech_paths = merged_paths(
        [
            item.get("path")
            for item in profile.get("evidence_index", [])
            if str(item.get("path", "")).startswith(("tech_stack.", "data_model.entities."))
        ][:12],
        pack.get("chapter_focus", {}).get("ch4", {}).get("recommended_paths", []),
        12,
    )
    tech_keywords = [item.get("topic", "") for item in tech_decisions]
    tech_keywords.extend([entity.get("name", "") for entity in entities])
    matched_shots = pick_matching_screenshots(shots, tech_keywords, "4.", limit=3)
    return {
        "chapter_id": "ch4",
        "title": "系统设计",
        "goal": "把系统怎么设计、为什么这样设计、设计如何支撑业务讲清楚，同时把架构图和 ER 图拆成可编辑产物交给用户确认。",
        "write_order": [
            "先解释系统整体结构，再说明前后端、数据库、认证或部署方案为什么这样搭配。",
            "接着说明核心实体、表结构或接口边界如何支撑主要业务流程。",
            "如果数据表较多，明确拆分多张 ER 图，避免一张图塞满所有信息。",
        ],
        "must_answer": [
            "系统采用了什么架构，为什么适合这个本科项目？",
            "后端、前端、数据库或认证方案为什么这样选？",
            "哪些实体或接口是核心，它们分别承担什么作用？",
        ],
        "evidence_paths": [{"path": path, "files": evidence_map.get(path, [])} for path in tech_paths],
        "tech_choice_prompts": [
            {
                "topic": item.get("topic"),
                "prompt": item.get("suggested_prompt") or f"说明为什么选用 {item.get('topic')}。",
                "observed_from": item.get("observed_from", []),
            }
            for item in tech_decisions
        ],
        "entity_targets": [
            {
                "name": entity.get("name"),
                "table": entity.get("table"),
                "field_count": len(entity.get("fields", [])),
                "suggested_path": f"data_model.entities.{entity.get('name')}",
            }
            for entity in entities
        ],
        "diagram_tasks": chapter_diagrams(pack, "ch4"),
        "brainstorm_tasks": chapter_brainstorm_tasks(pack, "ch4"),
        "required_user_actions": chapter_actions(pack, "review-drawio"),
        "screenshot_suggestions": [make_screenshot_payload(asset, "ch4") for asset in matched_shots],
        "defense_points": [
            "强调这个设计方案是为了让系统更容易开发和维护，不要空喊高并发、高可用。",
            "如果用了权限、登录拦截、数据库分层，要说明它们分别帮你解决了什么实际问题。",
        ],
    }


def build_ch5_kit(profile: dict, pack: dict, shots: list[dict], evidence_map: dict[str, list[str]]) -> dict:
    modules = top_modules(profile, limit=6)
    kit_modules = []
    used_shot_ids = set()
    for module in modules:
        module_path = f"modules.{slugify(module.get('name'))}"
        related_paths = [module_path]
        for api in module.get("apis", [])[:3]:
            method, _, route = api.partition(" ")
            related_paths.append(f"apis.{method.lower()}_{slugify(route)}")
        related_pages = related_frontend_pages(profile, module)
        for page in related_pages:
            related_paths.append(f"frontend_pages.{slugify(page.get('name'))}")
        module_shots = [
            asset
            for asset in pick_matching_screenshots(
                shots,
                module_keywords(module),
                "5.",
                limit=3,
                usage_phase="implementation",
            )
            if asset.get("id") not in used_shot_ids
        ][:2]
        for asset in module_shots:
            if asset.get("id"):
                used_shot_ids.add(asset["id"])
        kit_modules.append(
            {
                "module": module.get("name"),
                "responsibility": module.get("responsibility"),
                "key_classes": module.get("key_classes", [])[:4],
                "key_files": module.get("key_files", [])[:4],
                "apis": module.get("apis", [])[:4],
                "service_methods": module.get("service_methods", [])[:6],
                "frontend_pages": [
                    {
                        "name": page.get("name"),
                        "file": page.get("file"),
                        "route_hint": page.get("route_hint"),
                    }
                    for page in related_pages
                ],
                "suggested_paths": [
                    {"path": path, "files": evidence_map.get(path, [])}
                    for path in related_paths
                    if path in evidence_map or path == module_path
                ],
                "writing_prompt": (
                    f"先写“{module.get('name')} 模块主要完成什么业务”，"
                    "再结合 path 证据解释页面、接口或核心逻辑是怎么一步步做出来的，"
                    "最后补上与这段实现直接相关的页面截图、代码截图、配置截图或运行结果截图。"
                ),
                "implementation_story": [
                    "先交代你最先完成的是页面、接口还是数据结构。",
                    "再写联调时遇到的卡点，以及你如何通过日志、断点、SQL 或配置排查。",
                    "最后说明修完之后如何验证结果，并用截图或代码片段落证据。",
                ],
                "screenshot_suggestions": [make_screenshot_payload(asset, "ch5") for asset in module_shots],
            }
        )

    fallback_shots = [
        asset
        for asset in pick_matching_screenshots(shots, ["页面", "功能", "代码", "接口", "管理", "模块"], "5.", limit=4)
        if asset.get("id") not in used_shot_ids
    ]
    return {
        "chapter_id": "ch5",
        "title": "系统实现",
        "goal": "把自己真实做过的模块、接口、页面和关键代码写出来，让老师能看到工作量，也能看见系统是怎么一步步开发出来的。",
        "write_order": [
            "先按模块写功能实现，再写关键接口、权限控制、数据处理或状态流转。",
            "每个模块至少给出一条 path 证据，必要时再补页面截图、代码截图、配置截图或运行结果截图。",
            "写完主要功能后，单独留一节说明开发阶段遇到的典型问题和解决过程。",
        ],
        "must_answer": [
            "这个模块具体做了什么？",
            "我主要写了哪些页面、接口、SQL、配置或业务逻辑？",
            "这些实现为什么能证明工作量？",
            "这个模块是按什么顺序开发出来的，中间遇到过什么问题？",
        ],
        "module_packets": kit_modules,
        "diagram_tasks": chapter_diagrams(pack, "ch5"),
        "brainstorm_tasks": chapter_brainstorm_tasks(pack, "ch5"),
        "required_user_actions": chapter_actions(pack, "upload-implementation-screenshots", "review-mermaid"),
        "implementation_story_prompts": pack.get("implementation_story_prompts", []),
        "general_screenshot_suggestions": [make_screenshot_payload(asset, "ch5") for asset in fallback_shots],
        "used_screenshot_ids": sorted(used_shot_ids),
        "defense_points": [
            "不要只写“实现了用户管理模块”，要继续写清楚页面、接口、数据校验或权限逻辑。",
            "优先贴能证明你真的做过的截图，尤其是后台管理页、核心代码、配置和运行结果。",
        ],
    }


def build_ch6_kit(
    profile: dict,
    pack: dict,
    shots: list[dict],
    evidence_map: dict[str, list[str]],
    exclude_shot_ids: set[str] | None = None,
) -> dict:
    challenges = preferred_challenges(profile.get("challenge_log", []), limit=6)
    if not challenges:
        challenges = [
            {
                "title": "补充真实开发问题",
                "prompt": "回忆开发过程中出现过的报错、接口联调、权限判断、数据库字段不一致、分页查询或部署问题。",
                "symptom_prompt": "先写清楚问题最开始是怎么表现出来的。",
                "diagnosis_prompt": "再写你当时是如何排查和定位的。",
                "fix_prompt": "接着写最后改了什么。",
                "result_prompt": "最后写修复后如何验证通过。",
            }
        ]
    matched_shots = pick_matching_screenshots(
        shots,
        ["报错", "异常", "错误", "测试", "运行结果", "修复"],
        "6.",
        limit=5,
        usage_phase="debugging",
        exclude_ids=exclude_shot_ids,
    )
    evidence_paths = merged_paths(
        [
            item.get("path")
            for item in profile.get("evidence_index", [])
            if str(item.get("path", "")).startswith(("modules.", "apis.", "core_services.", "sql_artifacts.", "config_artifacts."))
        ][:14],
        pack.get("chapter_focus", {}).get("ch6", {}).get("recommended_paths", []),
        14,
    )
    return {
        "chapter_id": "ch6",
        "title": "系统测试与问题处理",
        "goal": "用真实问题、真实结果和真实截图证明系统被认真调试过，而不是只写一段空泛测试总结。",
        "write_order": [
            "先写主要功能如何验证，再写测试过程中遇到的问题和修复办法。",
            "如果没有完整性能测试，就写功能验证、联调过程、修复前后差异。",
            "截图要和问题或结果绑定，不要孤零零单放一张图。",
        ],
        "must_answer": [
            "主要功能是如何验证通过的？",
            "开发或测试阶段出现了哪些真实问题？",
            "这些问题是如何定位和修复的，修复后有什么变化？",
        ],
        "challenge_prompts": challenges,
        "challenge_sections": build_ch6_sections(challenges),
        "evidence_paths": [{"path": path, "files": evidence_map.get(path, [])} for path in evidence_paths],
        "diagram_tasks": chapter_diagrams(pack, "ch6"),
        "brainstorm_tasks": chapter_brainstorm_tasks(pack, "ch6"),
        "required_user_actions": chapter_actions(pack, "upload-debug-screenshots", "review-mermaid"),
        "screenshot_suggestions": [make_screenshot_payload(asset, "ch6") for asset in matched_shots],
        "defense_points": [
            "本科论文完全可以写真实报错和修复过程，这往往比空泛性能指标更有说服力。",
            "如果截图里体现了报错、修复后页面或测试结果，记得在正文里把因果关系说清楚。",
        ],
    }


def write_markdown(kit: dict):
    filename = {
        "ch3": "ch3-requirements.md",
        "ch4": "ch4-system-design.md",
        "ch5": "ch5-implementation.md",
        "ch6": "ch6-test-and-debug.md",
    }[kit["chapter_id"]]
    path = os.path.join(OUT_DIR, filename)
    lines = [
        f"# {kit['chapter_id']} {kit['title']}写作包",
        "",
        f"- 生成时间：{now_iso()}",
        f"- 本章目标：{kit['goal']}",
        "",
        "## 建议写作顺序",
        "",
    ]
    for item in kit.get("write_order", []):
        lines.append(f"- {item}")

    lines.extend(["", "## 建议回答问题", ""])
    for item in kit.get("must_answer", []):
        lines.append(f"- {item}")

    if kit.get("required_user_actions"):
        lines.extend(["", "## 等待用户补充的材料", ""])
        for item in kit["required_user_actions"]:
            lines.append(f"- {item['title']}: {item['why']}")
            lines.append(f"  expected_input: {item['expected_input']}")
            lines.append(f"  done_when: {item['done_when']}")

    if kit.get("diagram_tasks"):
        lines.extend(["", "## 图表任务", ""])
        for item in kit["diagram_tasks"]:
            lines.append(f"- {item['title']} ({item['delivery']})")
            lines.append(f"  save_to: `{item['save_to']}`")
            lines.append(f"  why: {item['why']}")
            if item.get("depends_on"):
                lines.append(f"  depends_on: {', '.join(item['depends_on'])}")
            lines.append("  placeholder: [TODO: 插入图表，待用户确认后替换]")

    if kit.get("brainstorm_tasks"):
        lines.extend(["", "## Brainstorm 触发点", ""])
        for item in kit["brainstorm_tasks"]:
            lines.append(f"- {item['id']}: {item['when_to_use']}")
            lines.append(f"  preferred_skill: {item['preferred_skill']}")
            lines.append(f"  fallback: {item['fallback']}")
            lines.append(f"  goal: {item['goal']}")
            for output in item.get("expected_output", []):
                lines.append(f"  expected_output: {output}")

    if kit.get("tech_choice_prompts"):
        lines.extend(["", "## 技术选型提示", ""])
        for item in kit["tech_choice_prompts"]:
            lines.append(f"- {item['topic']}: {item['prompt']}")

    if kit.get("entity_targets"):
        lines.extend(["", "## 实体与数据结构", ""])
        for item in kit["entity_targets"]:
            lines.append(f"- {item['name']} ({item['table']}): path `{item['suggested_path']}`，字段数 {item['field_count']}")

    if kit.get("module_packets"):
        lines.extend(["", "## 模块写作包", ""])
        for item in kit["module_packets"]:
            lines.append(f"### {item['module']}")
            lines.append("")
            lines.append(f"- 写作提示：{item['writing_prompt']}")
            for story in item.get("implementation_story", []):
                lines.append(f"- 实现过程：{story}")
            for path_item in item.get("suggested_paths", []):
                lines.append(f"- path: `{path_item['path']}`")
                for file in path_item.get("files", [])[:2]:
                    lines.append(f"  evidence: `{file}`")
            for api in item.get("apis", []):
                lines.append(f"- API: `{api}`")
            for method in item.get("service_methods", []):
                lines.append(f"- 服务方法: `{method}`")
            for page in item.get("frontend_pages", []):
                lines.append(f"- 页面: `{page.get('file')}`")
                if page.get("route_hint"):
                    lines.append(f"  route_hint: `{page.get('route_hint')}`")
            for shot in item.get("screenshot_suggestions", []):
                lines.append(f"- 截图 `{shot['id']}`: {shot['caption']}")
                if shot.get("proof_note"):
                    lines.append(f"  证明点：{shot['proof_note']}")
                lines.append(f"  示例句：{shot['example_sentence']}")
            lines.append("")

    if kit.get("challenge_prompts"):
        lines.extend(["", "## 问题与修复提示", ""])
        for item in kit["challenge_prompts"]:
            if item.get("prompt"):
                lines.append(f"- {item.get('title')}: {item['prompt']}")
            else:
                lines.append(f"- {item.get('title') or item}")
            for key, label in (
                ("symptom_prompt", "现象"),
                ("diagnosis_prompt", "排查"),
                ("fix_prompt", "修复"),
                ("result_prompt", "结果"),
            ):
                if item.get(key):
                    lines.append(f"  {label}: {item[key]}")
            if item.get("defense_angle"):
                lines.append(f"  答辩价值: {item['defense_angle']}")
            for observed in item.get("observed_from", [])[:3]:
                lines.append(f"  observed_from: `{observed}`")

    if kit.get("challenge_sections"):
        lines.extend(["", "## 建议小节结构", ""])
        for item in kit["challenge_sections"]:
            lines.append(f"### {item['heading']}")
            lines.append("")
            if item.get("summary"):
                lines.append(f"- 小节概述：{item['summary']}")
            for key, label in (
                ("symptom_prompt", "现象"),
                ("diagnosis_prompt", "排查"),
                ("fix_prompt", "修复"),
                ("result_prompt", "结果"),
            ):
                if item.get(key):
                    lines.append(f"- {label}：{item[key]}")
            if item.get("defense_angle"):
                lines.append(f"- 答辩价值：{item['defense_angle']}")
            for observed in item.get("observed_from", [])[:3]:
                lines.append(f"- observed_from: `{observed}`")
            lines.append("")

    if kit.get("evidence_paths"):
        lines.extend(["", "## 证据路径", ""])
        for item in kit["evidence_paths"]:
            lines.append(f"- `{item['path']}`")
            for file in item.get("files", [])[:3]:
                lines.append(f"  evidence: `{file}`")

    if kit.get("implementation_story_prompts"):
        lines.extend(["", "## 实现过程写法", ""])
        for item in kit["implementation_story_prompts"]:
            lines.append(f"- {item}")

    shot_items = kit.get("screenshot_suggestions") or kit.get("general_screenshot_suggestions") or []
    if shot_items:
        lines.extend(["", "## 截图自然引用建议", ""])
        for item in shot_items:
            lines.append(f"- `{item['id']}` {item['caption']}")
            if item.get("proof_note"):
                lines.append(f"  证明点：{item['proof_note']}")
            lines.append(f"  示例句：{item['example_sentence']}")

    lines.extend(["", "## 答辩提示", ""])
    for item in kit.get("defense_points", []):
        lines.append(f"- {item}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Build chapter-level writing kits from profile, evidence pack, and screenshots."
    )
    parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    profile = load_required_profile()
    pack = load_json(PACK_PATH, {})
    assets = load_json(MANIFEST_PATH, [])
    shots = collect_manual_screenshots(assets)
    evidence_map = evidence_lookup(profile)

    ch3_kit = build_ch3_kit(profile, pack, shots, evidence_map)
    ch4_kit = build_ch4_kit(profile, pack, shots, evidence_map)
    ch5_kit = build_ch5_kit(profile, pack, shots, evidence_map)
    ch6_kit = build_ch6_kit(
        profile,
        pack,
        shots,
        evidence_map,
        exclude_shot_ids=set(ch5_kit.get("used_screenshot_ids", [])),
    )
    kits = [ch3_kit, ch4_kit, ch5_kit, ch6_kit]

    index = {
        "generated_at": now_iso(),
        "repo_root": profile.get("repo_root"),
        "manual_screenshot_count": len(shots),
        "kits": kits,
    }
    with open(OUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    for kit in kits:
        write_markdown(kit)

    if os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        combined_actions = merge_required_user_actions(
            pack.get("required_user_actions", []),
            *[kit.get("required_user_actions", []) for kit in kits],
        )
        summary = (
            "已生成章节写作包，请先检查 chapter-kits/index.json、ch3-requirements.md、"
            "ch4-system-design.md、ch5-implementation.md、ch6-test-and-debug.md，"
            "并按清单补截图、Mermaid 与 draw.io 产物。"
        )
        update_collaboration_state(
            thesis,
            current_gate="phase-1-project-kits",
            waiting_for_user=True,
            required_user_actions=combined_actions,
            last_agent_summary=summary,
        )
        save_thesis_json(THESIS_PATH, thesis)

    print(f"[ok] chapter kit index written: {OUT_INDEX}")
    for kit in kits:
        filename = {
            "ch3": "ch3-requirements.md",
            "ch4": "ch4-system-design.md",
            "ch5": "ch5-implementation.md",
            "ch6": "ch6-test-and-debug.md",
        }[kit["chapter_id"]]
        print(f"[ok] chapter kit written: {os.path.join(OUT_DIR, filename)}")


if __name__ == "__main__":
    main()
