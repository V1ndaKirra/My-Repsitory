"""Build a defense-oriented evidence pack from project/profile.json.

Outputs:
  - project/undergrad-evidence-pack.json
  - project/undergrad-evidence-pack.md
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from thesis_schema import load_thesis_json, save_thesis_json, update_collaboration_state


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
PROFILE_PATH = os.path.join(ROOT, "project", "profile.json")
JSON_OUT = os.path.join(ROOT, "project", "undergrad-evidence-pack.json")
MD_OUT = os.path.join(ROOT, "project", "undergrad-evidence-pack.md")
THESIS_PATH = os.path.join(ROOT, "thesis.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        raise SystemExit(f"[error] profile not found: {PROFILE_PATH}")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def chunked(items: list[dict], size: int) -> list[list[dict]]:
    if size <= 0:
        return [items]
    return [items[idx: idx + size] for idx in range(0, len(items), size)]


def slugify(text: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "")).strip("-").lower()
    return slug or "item"


def build_screenshot_targets(modules: list[dict]) -> list[dict]:
    targets = []
    for module in modules[:8]:
        name = module.get("name") or "核心模块"
        targets.append(
            {
                "module": name,
                "usage_phase": "implementation",
                "why_capture": "用页面、代码、配置或运行结果截图证明这个模块真实实现过。",
                "suggested_caption": f"{name} 功能截图",
                "suggested_ref": f"待用户补图后，可在正文中写成：如 {{fig:shot-xx}} 所示，{name} 模块已经能够完成对应业务操作。",
                "preferred_sources": [
                    "页面功能截图",
                    "核心代码截图",
                    "运行结果截图",
                    "配置截图",
                ],
            }
        )
    return targets


def build_debug_screenshot_targets(challenges: list[dict]) -> list[dict]:
    targets = []
    for item in challenges[:4]:
        title = item.get("title") or "real-debug-issue"
        targets.append(
            {
                "title": title,
                "usage_phase": "debugging",
                "why_capture": "第六章要使用独立的问题处理截图，证明报错、排查和修复都真实发生过。",
                "suggested_caption": f"{title} 问题处理截图",
                "expected_bundle": [
                    "1 张报错或异常截图",
                    "1 张排查过程或日志截图",
                    "1 张修复后结果截图",
                ],
            }
        )
    return targets


def build_diagram_tasks(profile: dict, entities: list[dict], modules: list[dict]) -> list[dict]:
    tasks = [
        {
            "id": "req-business-flow",
            "chapter": "ch3",
            "type": "flowchart",
            "delivery": "mermaid",
            "title": "核心业务流程图",
            "why": "用于需求分析和业务流程分析，先交付 Mermaid 代码给用户检查。",
            "save_to": "assets/figures/fig-business-flow.mmd",
            "depends_on": ["真实页面流程", "真实接口调用", "真实状态流转"],
            "evidence_paths": ["modules", "apis", "frontend_pages"],
            "stop_after_delivery": True,
        },
        {
            "id": "module-overview",
            "chapter": "ch3",
            "type": "module_tree",
            "delivery": "drawio",
            "title": "系统功能模块图",
            "why": "用于说明系统边界和模块划分。",
            "save_to": "assets/figures/fig-module-tree.drawio",
            "depends_on": ["真实模块划分", "真实页面和接口"],
            "evidence_paths": ["modules", "frontend_pages", "apis"],
            "stop_after_delivery": True,
        },
        {
            "id": "arch-overview",
            "chapter": "ch4",
            "type": "architecture",
            "delivery": "drawio",
            "title": "系统总体架构图",
            "why": "说明前端、后端、数据库和部署边界之间的关系。",
            "save_to": "assets/figures/fig-arch-overview.drawio",
            "depends_on": ["真实技术栈", "真实服务边界", "真实部署方式"],
            "evidence_paths": ["tech_stack", "modules", "config_artifacts"],
            "stop_after_delivery": True,
        },
    ]

    entity_groups = chunked(entities[:18], 6)
    for idx, group in enumerate(entity_groups, 1):
        names = [item.get("name") for item in group if item.get("name")]
        tasks.append(
            {
                "id": f"er-split-{idx}",
                "chapter": "ch4",
                "type": "er_diagram",
                "delivery": "drawio",
                "title": f"ER 图分片 {idx}",
                "why": "数据表较多时拆成多张 ER 图，避免一张图塞满所有信息。",
                "save_to": f"assets/figures/fig-er-split-{idx}.drawio",
                "depends_on": names,
                "evidence_paths": [f"data_model.entities.{name}" for name in names],
                "stop_after_delivery": True,
            }
        )

    for module in modules[:6]:
        name = module.get("name") or "模块"
        tasks.append(
            {
                "id": f"impl-flow-{slugify(name)}",
                "chapter": "ch5",
                "type": "flowchart",
                "delivery": "mermaid",
                "title": f"{name} 实现流程图",
                "why": "把一个核心模块从页面/接口到服务/数据处理的实现链路画出来。",
                "save_to": f"assets/figures/fig-{slugify(name)}-impl-flow.mmd",
                "depends_on": [name, "真实代码路径", "真实接口或页面"],
                "evidence_paths": [f"modules.{slugify(name)}"],
                "stop_after_delivery": True,
            }
        )

    if profile.get("challenge_log"):
        tasks.append(
            {
                "id": "debug-flow",
                "chapter": "ch6",
                "type": "flowchart",
                "delivery": "mermaid",
                "title": "问题排查与修复流程图",
                "why": "把真实问题的发现、定位、修复和验证过程画出来。",
                "save_to": "assets/figures/fig-debug-flow.mmd",
                "depends_on": ["真实报错", "真实排查动作", "真实修复结果"],
                "evidence_paths": ["challenge_log", "modules", "config_artifacts"],
                "stop_after_delivery": True,
            }
        )

    return tasks


def build_required_user_actions(
    profile: dict,
    screenshot_targets: list[dict],
    debug_screenshot_targets: list[dict],
    diagram_tasks: list[dict],
) -> list[dict]:
    repo_root = profile.get("repo_root") or ""
    screenshot_modules = [item["module"] for item in screenshot_targets[:4]]
    debug_titles = [item["title"] for item in debug_screenshot_targets[:3] if item.get("title")]
    diagram_targets = [item["save_to"] for item in diagram_tasks[:4]]
    return [
        {
            "kind": "confirm-repo-root",
            "title": "确认项目地址",
            "why": "后续所有代码、图表和证据都必须从这个项目路径出发。",
            "expected_input": repo_root or "用户提供项目根目录",
            "done_when": "用户明确确认 repo 路径无误。",
        },
        {
            "kind": "provide-zh-pdfs",
            "title": "提供中文文献目录",
            "why": "中文文献优先由用户自行下载，再交给 skill 入库。",
            "expected_input": "用户提供中文 PDF 下载目录",
            "done_when": "运行 literature_import_pdfs.py --dir <用户目录> 后 metadata 已更新。",
        },
        {
            "kind": "upload-implementation-screenshots",
            "title": "补充第五章实现截图",
            "why": "第五章要体现系统是如何一步步实现出来的，必须有页面、代码、配置或运行结果截图。",
            "expected_input": f"至少覆盖这些模块：{', '.join(screenshot_modules) if screenshot_modules else '核心模块'}",
            "done_when": "截图已放入 assets/screenshots，并登记到 assets/manifest.json。",
        },
        {
            "kind": "upload-debug-screenshots",
            "title": "补充第六章问题处理截图",
            "why": "第六章不能直接复用第五章的功能展示图，必须补充独立的报错、排查和修复后结果截图。",
            "expected_input": (
                f"优先围绕：{', '.join(debug_titles)}；每个真实问题最好 2-3 张图。"
                if debug_titles
                else "每个真实问题至少补 2-3 张图，覆盖报错、排查和修复后结果。"
            ),
            "done_when": "报错/排查/修复后结果截图已放入 assets/screenshots，并登记到 assets/manifest.json。",
        },
        {
            "kind": "review-mermaid",
            "title": "处理 Mermaid 流程图",
            "why": "流程图先交付 Mermaid 代码，用户复制到 draw.io 后还能继续编辑。",
            "expected_input": ", ".join(diagram_targets[:2]) if diagram_targets else "assets/figures/*.mmd",
            "done_when": "用户已保存编辑后的文件并回传工作区路径。",
        },
        {
            "kind": "review-drawio",
            "title": "检查 draw.io 图",
            "why": "ER 图、架构图、部署图、组件图、用例图应以 .drawio 文件交付。",
            "expected_input": ", ".join(diagram_targets[2:4]) if len(diagram_targets) > 2 else "assets/figures/*.drawio",
            "done_when": "用户确认图中元素、命名和关系都来自真实项目。",
        },
    ]


def build_brainstorm_tasks(modules: list[dict], challenge_log: list[dict]) -> list[dict]:
    tasks = [
        {
            "id": "implementation-story-replay",
            "chapter": "ch5",
            "preferred_skill": "superpowers brainstorm",
            "fallback": "普通对话引导",
            "when_to_use": "用户知道模块做过，但不知道如何按开发顺序写出实现过程时。",
            "goal": "把核心模块拆成“先做什么 -> 后做什么 -> 卡在哪 -> 怎么验证”的可写结构。",
            "expected_output": [
                "开发顺序",
                "关键代码路径",
                "建议截图清单",
                "正文写法草稿",
            ],
        },
        {
            "id": "debug-story-replay",
            "chapter": "ch6",
            "preferred_skill": "superpowers brainstorm",
            "fallback": "普通对话引导",
            "when_to_use": "challenge_log 里已有问题线索，但 symptom / diagnosis / fix / result 还说不清时。",
            "goal": "优先围绕核心业务或关键实现问题，整理成可答辩的排查链路。",
            "expected_output": [
                "现象",
                "排查步骤",
                "修复动作",
                "结果验证",
            ],
        },
    ]

    for module in modules[:4]:
        name = module.get("name") or "模块"
        tasks.append(
            {
                "id": f"impl-module-{slugify(name)}",
                "chapter": "ch5",
                "preferred_skill": "superpowers brainstorm",
                "fallback": "普通对话引导",
                "when_to_use": f"准备写 {name} 模块，但页面、接口、服务、SQL 的叙述顺序容易混乱时。",
                "goal": f"围绕 {name} 模块生成一个不编造事实的实现过程提纲。",
                "expected_output": [
                    "模块边界",
                    "开发顺序",
                    "关键文件",
                    "最值得补的截图",
                ],
            }
        )

    if challenge_log:
        tasks.append(
            {
                "id": "debug-screenshot-planning",
                "chapter": "ch6",
                "preferred_skill": "superpowers brainstorm",
                "fallback": "普通对话引导",
                "when_to_use": "已经知道有真实问题，但还不确定优先补哪些调试截图时。",
                "goal": "生成最小截图清单，优先保留最能证明工作量的图。",
                "expected_output": [
                    "截图优先级",
                    "每张图证明点",
                    "对应章节",
                    "建议图注",
                ],
            }
        )

    return tasks


def build_pack(profile: dict) -> dict:
    modules = profile.get("modules", [])
    tech_decisions = profile.get("tech_decisions", [])
    entities = profile.get("data_model", {}).get("entities", [])
    evidence_index = profile.get("evidence_index", [])
    challenge_log = profile.get("challenge_log", [])

    screenshot_targets = build_screenshot_targets(modules)
    debug_screenshot_targets = build_debug_screenshot_targets(challenge_log)
    diagram_tasks = build_diagram_tasks(profile, entities, modules)
    required_user_actions = build_required_user_actions(
        profile,
        screenshot_targets,
        debug_screenshot_targets,
        diagram_tasks,
    )
    brainstorm_tasks = build_brainstorm_tasks(modules, challenge_log)

    chapter_focus = {
        "ch3": {
            "title": "需求分析",
            "must_cover": [
                "核心业务目标和主要使用角色",
                "系统功能模块划分",
                "至少一个真实业务流程或状态流转",
                "需求分析如何衔接后续系统设计",
            ],
            "recommended_paths": [
                item["path"]
                for item in evidence_index
                if item.get("path", "").startswith(("modules.", "frontend_pages.", "apis."))
            ][:12],
        },
        "ch4": {
            "title": "系统设计",
            "must_cover": [
                "总体架构设计及其原因",
                "数据库设计与实体关系",
                "关键流程或接口设计",
                "技术选型理由",
            ],
            "recommended_paths": [
                item["path"]
                for item in evidence_index
                if item.get("path", "").startswith(("tech_stack.", "data_model.entities.", "modules.", "config_artifacts."))
            ][:12],
        },
        "ch5": {
            "title": "系统实现",
            "must_cover": [
                "自己完成的核心功能模块",
                "关键接口、页面或业务逻辑",
                "实现证据路径",
                "自然引用的截图说明",
                "一步步开发出来的过程",
            ],
            "recommended_paths": [
                item["path"]
                for item in evidence_index
                if item.get("path", "").startswith(("modules.", "apis.", "frontend_pages.", "sql_artifacts.", "config_artifacts."))
            ][:18],
        },
        "ch6": {
            "title": "系统测试与问题处理",
            "must_cover": [
                "功能验证过程",
                "真实问题及排查过程",
                "修复前后结果",
                "独立于第五章的报错/排查/修复后截图",
            ],
            "recommended_paths": [
                item["path"]
                for item in evidence_index
                if item.get("path", "").startswith(("modules.", "apis.", "data_model.entities.", "sql_artifacts.", "config_artifacts.", "core_services."))
            ][:12],
        },
    }

    pack = {
        "generated_at": now_iso(),
        "repo_root": profile.get("repo_root"),
        "module_highlights": [
            {
                "module": m.get("name"),
                "evidence_files": m.get("key_files", [])[:3],
                "apis": m.get("apis", [])[:5],
                "suggested_path": f"modules.{slugify(m.get('name'))}",
            }
            for m in modules[:10]
        ],
        "tech_choice_prompts": [
            {
                "topic": d.get("topic"),
                "prompt": d.get("suggested_prompt") or f"Explain why {d.get('topic')} was chosen.",
                "observed_from": d.get("observed_from", []),
            }
            for d in tech_decisions[:12]
        ],
        "data_model_targets": [
            {
                "entity": e.get("name"),
                "table": e.get("table"),
                "field_count": len(e.get("fields", [])),
                "suggested_path": f"data_model.entities.{e.get('name')}",
            }
            for e in entities[:12]
        ],
        "challenge_candidates": [
            {
                "title": item.get("title"),
                "prompt": item.get("prompt"),
                "observed_from": item.get("observed_from", []),
                "category": item.get("category"),
                "focus": item.get("focus"),
                "priority": item.get("priority"),
                "symptom_prompt": item.get("symptom_prompt"),
                "diagnosis_prompt": item.get("diagnosis_prompt"),
                "fix_prompt": item.get("fix_prompt"),
                "result_prompt": item.get("result_prompt"),
                "defense_angle": item.get("defense_angle"),
            }
            for item in challenge_log[:8]
        ],
        "screenshot_targets": screenshot_targets,
        "debug_screenshot_targets": debug_screenshot_targets,
        "diagram_tasks": diagram_tasks,
        "brainstorm_tasks": brainstorm_tasks,
        "required_user_actions": required_user_actions,
        "chapter_focus": chapter_focus,
        "implementation_story_prompts": [
            "按“先搭页面/接口骨架 -> 接业务逻辑 -> 联调 -> 修问题 -> 验证结果”的顺序回写系统实现过程。",
            "每个核心模块至少补一条真实代码路径和一张截图，截图可以是页面、配置、代码或运行结果。",
            "如果一个难点讲不清，就拆成 symptom -> diagnosis -> fix -> result 四步，不要只写最终效果。",
            "第六章的问题处理图和截图要独立于第五章功能实现图，优先补报错、排查、修复后对比图。",
        ],
        "writing_rules": [
            "Prefer concrete project details over abstract claims.",
            "Use screenshots naturally inside explanation sentences.",
            "Explain tech choice in plain undergrad-friendly language.",
            "Describe at least one real problem and how it was solved.",
            "Prefer core business or implementation problems over environment setup issues in chapter 6.",
            "Do not summarize an English paper's contribution when abstract and full text are both unavailable.",
            "Prefer page files, SQL files, and config files as workload evidence when they are part of what you implemented.",
            "Pause after each major artifact and wait for user confirmation before moving on.",
        ],
    }
    return pack


def write_pack(pack: dict):
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    lines = []
    lines.append("# Undergrad Evidence Pack")
    lines.append("")
    lines.append(f"- Generated: {pack['generated_at']}")
    lines.append(f"- Repo Root: `{pack.get('repo_root', '')}`")
    lines.append("")

    lines.append("## Required User Actions")
    lines.append("")
    for item in pack.get("required_user_actions", []):
        lines.append(f"- {item['title']}: {item['why']}")
        lines.append(f"  expected_input: {item['expected_input']}")
        lines.append(f"  done_when: {item['done_when']}")
    lines.append("")

    lines.append("## Diagram Tasks")
    lines.append("")
    for item in pack.get("diagram_tasks", []):
        lines.append(f"- {item['title']} ({item['delivery']} -> `{item['save_to']}`)")
        lines.append(f"  chapter: `{item['chapter']}`")
        lines.append(f"  why: {item['why']}")
        if item.get("depends_on"):
            lines.append(f"  depends_on: {', '.join(item['depends_on'])}")
    lines.append("")

    lines.append("## Brainstorm Tasks")
    lines.append("")
    for item in pack.get("brainstorm_tasks", []):
        lines.append(f"- {item['id']} ({item['chapter']}): {item['when_to_use']}")
        lines.append(f"  preferred_skill: {item['preferred_skill']}")
        lines.append(f"  fallback: {item['fallback']}")
        lines.append(f"  goal: {item['goal']}")
    lines.append("")

    lines.append("## Module Highlights")
    lines.append("")
    for item in pack.get("module_highlights", []):
        lines.append(f"- {item['module']}:")
        lines.append(f"  path: `{item['suggested_path']}`")
        if item.get("evidence_files"):
            lines.append(f"  evidence: `{item['evidence_files'][0]}`")
        if item.get("apis"):
            lines.append(f"  api sample: `{item['apis'][0]}`")
    lines.append("")

    lines.append("## Challenge Candidates")
    lines.append("")
    for item in pack.get("challenge_candidates", []):
        lines.append(f"- {item['title']}: {item['prompt']}")
        lines.append(f"  focus: `{item.get('focus', '')}`")
        if item.get("priority") is not None:
            lines.append(f"  priority: `{item['priority']}`")
        for observed in item.get("observed_from", [])[:3]:
            lines.append(f"  observed_from: `{observed}`")
    lines.append("")

    lines.append("## Screenshot Targets")
    lines.append("")
    for item in pack.get("screenshot_targets", []):
        lines.append(f"- [{item['usage_phase']}] {item['module']}: {item['suggested_caption']}")
        lines.append(f"  why_capture: {item['why_capture']}")
    for item in pack.get("debug_screenshot_targets", []):
        lines.append(f"- [{item['usage_phase']}] {item['title']}: {item['suggested_caption']}")
        lines.append(f"  why_capture: {item['why_capture']}")
        for bundle in item.get("expected_bundle", []):
            lines.append(f"  expected_bundle: {bundle}")
    lines.append("")

    lines.append("## Chapter Focus")
    lines.append("")
    for cid, item in pack.get("chapter_focus", {}).items():
        lines.append(f"### {cid} {item['title']}")
        lines.append("")
        for bullet in item.get("must_cover", []):
            lines.append(f"- {bullet}")
        lines.append("Suggested paths:")
        for path in item.get("recommended_paths", [])[:8]:
            lines.append(f"- `{path}`")
        lines.append("")

    lines.append("## Writing Rules")
    lines.append("")
    for item in pack.get("writing_rules", []):
        lines.append(f"- {item}")
    lines.append("")

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    profile = load_profile()
    pack = build_pack(profile)
    write_pack(pack)
    if os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        summary = (
            "已生成项目证据包，请先检查 project/undergrad-evidence-pack.json 和 "
            "project/undergrad-evidence-pack.md，确认难点候选、图表任务和待补材料清单。"
        )
        update_collaboration_state(
            thesis,
            current_gate="phase-1-project-evidence",
            waiting_for_user=True,
            required_user_actions=pack.get("required_user_actions", []),
            last_agent_summary=summary,
        )
        save_thesis_json(THESIS_PATH, thesis)
    print(f"[ok] evidence pack written: {JSON_OUT}")
    print(f"[ok] evidence pack written: {MD_OUT}")


if __name__ == "__main__":
    main()
