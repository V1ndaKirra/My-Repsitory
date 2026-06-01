# -*- coding: utf-8 -*-
r"""Initialize an undergrad-thesis workspace for the thesis-writing skill.

Creates the standard directory structure, copies template files, and writes a
starter thesis.json aligned with the current undergrad-defense-oriented skill.

Usage:
  python scripts/init_workspace.py --root E:\Thesis\demo
  python scripts/init_workspace.py --root E:\Thesis\demo --title "医院门诊系统设计与实现"
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from thesis_schema import default_collaboration, default_context_bridge, default_user_inputs


SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def write_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def copy_if_missing(src: str, dst: str):
    if not os.path.exists(dst):
        shutil.copy2(src, dst)


def default_outline() -> list[dict]:
    return [
        {
            "id": "ch0",
            "title": "摘要",
            "draft_path": "drafts/00-abstract.md",
            "word_budget": 800,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
        {
            "id": "ch1",
            "title": "绪论",
            "draft_path": "drafts/01-introduction.md",
            "word_budget": 2000,
            "word_actual": 0,
            "status": "planned",
            "subsections": [
                {"id": "ch1.1", "title": "课题背景与意义"},
                {"id": "ch1.2", "title": "相关研究与技术概况"},
                {"id": "ch1.3", "title": "论文主要工作"},
            ],
        },
        {
            "id": "ch2",
            "title": "相关技术",
            "draft_path": "drafts/02-related-work.md",
            "word_budget": 1800,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
        {
            "id": "ch3",
            "title": "需求分析",
            "draft_path": "drafts/03-requirements.md",
            "word_budget": 2200,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
        {
            "id": "ch4",
            "title": "系统设计",
            "draft_path": "drafts/04-system-design.md",
            "word_budget": 3200,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
        {
            "id": "ch5",
            "title": "系统实现",
            "draft_path": "drafts/05-implementation.md",
            "word_budget": 4200,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
        {
            "id": "ch6",
            "title": "系统测试与问题处理",
            "draft_path": "drafts/06-system-test.md",
            "word_budget": 2400,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
        {
            "id": "ch7",
            "title": "总结与展望",
            "draft_path": "drafts/07-conclusion.md",
            "word_budget": 1200,
            "word_actual": 0,
            "status": "planned",
            "subsections": [],
        },
    ]


def default_thesis_meta(args) -> dict:
    return {
        "title": args.title or "",
        "school": args.school or "",
        "author": args.author or "",
        "major": args.major or "",
        "degree_level": "undergrad",
        "orientation": "undergrad-defense",
    }


def default_thesis_json(args) -> dict:
    return {
        "schema_version": "2",
        "current_phase": "phase-0-init",
        "phase_status": {
            "phase-0-init": "completed",
            "phase-1-project": "pending",
            "phase-2-literature": "pending",
            "phase-3-outline": "completed",
            "phase-4-drafting": "pending",
            "phase-5-assets": "pending",
            "phase-6-preflight": "pending",
            "phase-7-layout": "pending",
        },
        "meta": default_thesis_meta(args),
        "outline": default_outline(),
        "user_inputs": default_user_inputs(),
        "progress": {
            "phase": "init",
            "last_updated": now_iso(),
            "notes": [
                "已初始化本科毕设答辩导向工作区。",
                "后续优先补 project/profile.json、需求分析、系统设计、系统实现、测试与问题处理。",
            ],
        },
        "environment": {},
        "context_bridge": default_context_bridge(),
        "collaboration": default_collaboration(),
        "library": {
            "total_count": 0,
            "chinese_count": 0,
            "english_count": 0,
        },
        "project": {
            "status": "draft",
            "profile_path": "project/profile.json",
            "tech_decisions": [],
            "implementation_highlights": [],
            "challenge_log": [],
            "evidence_index": [],
        },
        "assets": {
            "figure_count": 0,
            "table_count": 0,
        },
        "last_outputs": {},
        "blocked_reason": None,
        "rerun_safe": True,
    }


def chapter_template(chapter_id: str, title: str) -> str:
    templates = {
        "ch0": (
            "## 摘要正文\n\n"
            "[TODO: 用较自然的本科论文口吻概述系统做了什么、用了哪些关键技术、完成了哪些核心功能。]\n"
        ),
        "ch1": (
            "## 1.1 课题背景与意义\n\n"
            "[TODO: 结合项目场景说明为什么要做这个系统，避免空泛大话。]\n\n"
            "## 1.2 相关研究与技术概况\n\n"
            "[TODO: 只写和本项目直接相关的研究或技术，控制引用量但保证真实。]\n\n"
            "## 1.3 论文主要工作\n\n"
            "[TODO: 明确写出自己完成了哪些模块、页面、接口、数据库设计和测试改进工作。]\n"
        ),
        "ch2": (
            "## 2.1 后端技术\n\n"
            "[TODO: 介绍项目真实用到的后端框架，并说明为什么选它。]\n\n"
            "## 2.2 前端技术\n\n"
            "[TODO: 介绍项目真实用到的前端框架，并说明为什么选它。]\n\n"
            "## 2.3 数据库与其他技术\n\n"
            "[TODO: 介绍数据库、认证、部署或辅助工具，避免写成百科。]\n"
        ),
        "ch3": (
            "## 3.1 系统角色与业务场景\n\n"
            "[TODO: 写清用户、管理员等角色以及他们分别要完成什么业务。]\n\n"
            "## 3.2 功能需求分析\n\n"
            "[TODO: 分模块说明功能需求。]\n\n"
            "## 3.3 非功能需求分析\n\n"
            "[TODO: 只写和本项目相关的性能、可用性、安全性要求。]\n"
        ),
        "ch4": (
            "## 4.1 总体架构设计\n\n"
            "[TODO: 说明系统采用什么架构，以及为什么这样设计。]\n"
            "如 {{fig:fig-arch-overview}} 所示，[TODO: 用一句话解释架构图在证明什么。]\n\n"
            "## 4.2 数据库设计\n\n"
            "[TODO: 写清核心数据表、字段关系与设计原因。]\n"
            "如 {{fig:fig-er-diagram}} 所示，[TODO: 说明数据库结构如何支撑业务流程。]\n\n"
            "## 4.3 技术选型说明\n\n"
            "[TODO: 分别说明框架、数据库、认证方案为什么这样选，尽量贴近本科项目实际。]\n"
        ),
        "ch5": (
            "## 5.1 核心功能实现\n\n"
            "[TODO: 先写这个模块做了什么，再补实现过程。]\n"
            "path: modules.example\n"
            "如 {{fig:shot-01}} 所示，[TODO: 自然说明这个页面/代码截图证明了什么，不要单独摆截图。]\n\n"
            "## 5.2 关键接口或业务逻辑实现\n\n"
            "[TODO: 解释接口、SQL、权限、状态流转等关键实现。]\n"
            "path: apis.example\n\n"
            "## 5.3 开发中的典型问题与解决\n\n"
            "[TODO: 写至少 1-2 个真实问题，包括问题现象、排查过程和最终解决方法。]\n"
        ),
        "ch6": (
            "## 6.1 功能测试\n\n"
            "[TODO: 用真实流程说明系统主要功能是否达到预期。]\n\n"
            "## 6.2 问题定位与修复\n\n"
            "[TODO: 重点写测试阶段发现的问题、如何定位、如何修复。]\n"
            "如 {{fig:shot-02}} 所示，[TODO: 自然解释报错截图、修复后截图或运行结果截图。]\n\n"
            "## 6.3 改进结果说明\n\n"
            "[TODO: 写修复后的效果。如果没有真实性能测试，不要硬编 QPS/TPS。]\n"
        ),
        "ch7": (
            "## 7.1 工作总结\n\n"
            "[TODO: 总结自己在需求、设计、实现、测试几个阶段完成了哪些工作。]\n\n"
            "## 7.2 不足与展望\n\n"
            "[TODO: 诚实写出现有不足和后续可以改进的方向。]\n"
        ),
    }
    return templates.get(chapter_id, f"## {title} 正文\n\n[TODO: 按本科毕设答辩导向补充本章内容]\n")


def seed_draft(path: str, chapter_id: str, title: str, word_budget: int):
    if os.path.exists(path):
        return
    content = (
        "---\n"
        f"chapter_id: {chapter_id}\n"
        f"title: {title}\n"
        f"word_budget: {word_budget}\n"
        "word_actual: 0\n"
        "status: planned\n"
        f"last_updated: {now_iso()}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{chapter_template(chapter_id, title)}"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(
        description="Initialize an undergrad-defense-oriented thesis workspace."
    )
    parser.add_argument("--root", required=True, help="Workspace root directory")
    parser.add_argument("--title", default="", help="Thesis title")
    parser.add_argument("--school", default="", help="School name")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--major", default="", help="Major name")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    dirs = [
        "project",
        os.path.join("library", "pdfs"),
        os.path.join("library", "fulltext"),
        os.path.join("library", "chapter-briefs"),
        "drafts",
        os.path.join("assets", "figures"),
        os.path.join("assets", "screenshots"),
        os.path.join("assets", "tables"),
        "template",
        "output",
    ]
    for rel in dirs:
        ensure_dir(os.path.join(root, rel))

    copy_if_missing(
        os.path.join(SKILL_ROOT, "template", "format-contract.json"),
        os.path.join(root, "template", "format-contract.json"),
    )
    copy_if_missing(
        os.path.join(SKILL_ROOT, "template", "original.docx"),
        os.path.join(root, "template", "original.docx"),
    )

    thesis_path = os.path.join(root, "thesis.json")
    if not os.path.exists(thesis_path):
        write_json(thesis_path, default_thesis_json(args))

    profile_path = os.path.join(root, "project", "profile.json")
    if not os.path.exists(profile_path):
        write_json(
            profile_path,
            {
                "status": "draft",
                "repo_root": "",
                "tech_stack": {"backend": [], "frontend": [], "database": []},
                "architecture": {},
                "modules": [],
                "data_model": {},
                "apis": {},
                "core_services": [],
                "scale": {},
                "tech_decisions": [],
                "implementation_highlights": [],
                "challenge_log": [],
                "evidence_index": [],
            },
        )

    for ch in default_outline():
        seed_draft(
            os.path.join(root, ch["draft_path"].replace("/", os.sep)),
            ch["id"],
            ch["title"],
            ch["word_budget"],
        )

    metadata_path = os.path.join(root, "library", "metadata.json")
    if not os.path.exists(metadata_path):
        write_json(metadata_path, [])
    bib_path = os.path.join(root, "library", "references.bib")
    if not os.path.exists(bib_path):
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write("")
    manifest_path = os.path.join(root, "assets", "manifest.json")
    if not os.path.exists(manifest_path):
        write_json(manifest_path, [])

    print(f"[ok] workspace initialized: {root}")
    print(f"[ok] thesis.json: {thesis_path}")
    print(f"[ok] profile.json: {profile_path}")


if __name__ == "__main__":
    main()
