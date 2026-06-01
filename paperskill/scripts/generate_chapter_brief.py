# -*- coding: utf-8 -*-
"""Generate Chapter Brief after a chapter is finalized.

A Chapter Brief is a ~300-word structured summary that captures the key
outputs, terminology, and decisions of a chapter. Subsequent writing sessions
load only the Briefs (not the full chapter texts), saving ~90% context budget.

Usage:
  python generate_chapter_brief.py --chapter ch3
  python generate_chapter_brief.py --chapter ch3 --draft drafts/03-requirements.md
  python generate_chapter_brief.py --all     # process all finalized chapters
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from thesis_schema import load_thesis_json, save_thesis_json

ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
THESIS_PATH = os.path.join(ROOT, "thesis.json")
BRIEFS_DIR = os.path.join(ROOT, "library", "chapter-briefs")
os.makedirs(BRIEFS_DIR, exist_ok=True)


def load_thesis() -> dict | None:
    if not os.path.exists(THESIS_PATH):
        print(f"[error] thesis.json not found at {THESIS_PATH}")
        return None
    return load_thesis_json(THESIS_PATH)


def save_thesis(thesis: dict):
    save_thesis_json(THESIS_PATH, thesis)


def find_chapter(thesis: dict, chapter_id: str) -> dict | None:
    for ch in thesis.get("outline", []):
        if ch.get("id") == chapter_id:
            return ch
    return None


def read_draft(draft_path: str) -> str | None:
    """Read a chapter draft, resolving relative to ROOT."""
    ap = os.path.join(ROOT, draft_path.replace("/", os.sep))
    if os.path.exists(ap):
        with open(ap, "r", encoding="utf-8") as f:
            return f.read()
    return None


def count_words(text: str) -> int:
    """Count Chinese + English characters/words for word budget."""
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"[A-Za-z]+", text))
    return chinese + english * 2


def extract_headings(text: str) -> list[str]:
    """Extract H2/H3 headings from markdown."""
    headings = []
    for m in re.finditer(r"^#{2,4}\s+(.+)$", text, re.MULTILINE):
        headings.append(m.group(1).strip())
    return headings


def extract_citations(text: str) -> list[str]:
    """Extract cite-keys from [@key] patterns."""
    keys = []
    for block in re.findall(r"\[@([^\]]+)\]", text):
        for part in block.split(","):
            k = part.strip().lstrip("@").strip()
            if k:
                keys.append(k)
    return sorted(set(keys))


def extract_terms(text: str) -> dict[str, str]:
    """Heuristic extraction of defined terms.

    Looks for patterns like:
      - "XXX是指/即/定义为..."
      - "XXX（英文全称）"
      - "XXX (XXX) 是..."
      - bolded terms **XXX**
    """
    terms = {}

    # Pattern 1: "XXX是指..." or "XXX即..."
    for m in re.finditer(
        r"([\u4e00-\u9fffA-Za-z]{2,20})\s*(?:是指|指的是|即|定义为|又称|也称为)\s*(.{10,120})",
        text):
        term = m.group(1).strip()
        definition = m.group(2).strip()
        if len(term) >= 2 and len(definition) >= 6:
            terms[term] = definition[:120]

    # Pattern 2: Bolded terms **XXX**
    for m in re.finditer(r"\*\*([\u4e00-\u9fffA-Za-z]{2,20})\*\*", text):
        term = m.group(1).strip()
        if term not in terms and len(term) >= 2:
            # Look for definition in the next sentence
            pos = m.end()
            next_text = text[pos:pos + 200]
            def_match = re.search(r"(?:是指|即|是|指的是)\s*(.{10,120})", next_text)
            if def_match:
                terms[term] = def_match.group(1).strip()[:120]
            else:
                terms[term] = "(术语，定义未明确提取)"

    return terms


def extract_outputs(text: str) -> list[str]:
    """Extract table/figure references and key deliverables."""
    outputs = []
    for m in re.finditer(r"\{\{(?:fig|tab|eq):([^}]+)\}\}", text):
        outputs.append(m.group(0))
    return sorted(set(outputs))


def extract_evidence_refs(text: str) -> list[str]:
    """Extract evidence paths such as `path: modules.order.controller`."""
    refs = []
    for m in re.finditer(r"(?im)^\s*path:\s*([^\n]+)", text):
        refs.append(m.group(1).strip().strip('"').strip("'"))
    return sorted(set(refs))


def extract_framework_mentions(text: str) -> list[str]:
    """Extract common framework/tool mentions useful for defense-oriented briefs."""
    catalog = [
        "Spring Boot", "Spring Cloud", "Spring Security", "Vue 3", "Vite",
        "Element Plus", "MyBatis-Plus", "MyBatis", "MySQL", "Redis", "JWT",
        "Axios", "Nginx", "Docker", "UniApp", "React", "Node.js", "Java",
        "Python", "Graphviz", "Tesseract",
    ]
    found = []
    lower_text = text.lower()
    for item in catalog:
        if item.lower() in lower_text:
            found.append(item)
    return found


def extract_decision_snippets(text: str) -> list[str]:
    """Extract short snippets about framework/technology selection rationale."""
    snippets = []
    for para in re.split(r"\n\s*\n", text):
        compact = re.sub(r"\s+", " ", para).strip()
        if not compact:
            continue
        if re.search(r"(选用|采用|选择|技术选型|框架选型|数据库选型)", compact) and \
           re.search(r"(因为|原因|考虑到|适合|便于|优势|优点|为了|满足)", compact):
            snippets.append(compact[:120])
    return snippets[:5]


def extract_challenge_solution_pairs(text: str) -> list[dict[str, str]]:
    """Extract challenge/solution snippets from adjacent or same paragraphs."""
    paragraphs = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n\s*\n", text)]
    paragraphs = [p for p in paragraphs if p]
    pairs = []
    challenge_re = re.compile(r"(难点|问题|瓶颈|报错|冲突|卡顿|失败|兼容性|性能问题)")
    solution_re = re.compile(r"(解决|处理|优化|修复|改为|通过|最终采用|排查)")
    for idx, para in enumerate(paragraphs):
        has_challenge = bool(challenge_re.search(para))
        has_solution = bool(solution_re.search(para))
        if has_challenge and has_solution:
            pairs.append({"challenge": para[:60], "solution": para[:120]})
        elif has_challenge and idx + 1 < len(paragraphs):
            nxt = paragraphs[idx + 1]
            if solution_re.search(nxt):
                pairs.append({"challenge": para[:60], "solution": nxt[:120]})
    return pairs[:5]


def generate_brief(draft_text: str, ch_info: dict) -> str:
    """Generate a natural-language summary of the chapter.
    This is a rule-based summary; can be replaced with an LLM call.
    """
    title = ch_info.get("title", "")
    headings = extract_headings(draft_text)
    terms = extract_terms(draft_text)
    word_count = count_words(draft_text)
    evidence_refs = extract_evidence_refs(draft_text)
    frameworks = extract_framework_mentions(draft_text)
    decisions = extract_decision_snippets(draft_text)
    challenges = extract_challenge_solution_pairs(draft_text)

    # Build a structured summary
    parts = [f"本章为「{title}」。"]

    if headings:
        main_sections = [h for h in headings if not h.startswith("#")]
        if main_sections:
            parts.append(f"主要内容包括：{'、'.join(main_sections[:6])}。")

    if terms:
        key_terms = list(terms.keys())[:5]
        parts.append(f"定义了关键术语：{'、'.join(key_terms)}。")

    if frameworks:
        parts.append(f"涉及的框架/工具包括：{'、'.join(frameworks[:6])}。")

    if evidence_refs:
        parts.append(f"引用了 {len(evidence_refs)} 处实现证据路径，可用于答辩时说明具体工作量。")

    if decisions:
        parts.append("文中给出了技术选型理由。")

    if challenges:
        parts.append(f"记录了 {len(challenges)} 处开发难点及解决过程。")

    parts.append(f"全章约{word_count}字。")

    return "".join(parts)


def generate_brief_file(chapter_id: str, draft_text: str,
                        ch_info: dict) -> dict:
    """Generate a Chapter Brief JSON file."""
    headings = extract_headings(draft_text)
    terms = extract_terms(draft_text)
    citations = extract_citations(draft_text)
    assets = extract_outputs(draft_text)
    evidence_refs = extract_evidence_refs(draft_text)
    frameworks = extract_framework_mentions(draft_text)
    decisions = extract_decision_snippets(draft_text)
    challenges = extract_challenge_solution_pairs(draft_text)
    word_count = count_words(draft_text)
    brief_text = generate_brief(draft_text, ch_info)

    brief = {
        "chapter_id": chapter_id,
        "title": ch_info.get("title", ""),
        "brief": brief_text,
        "defined_terms": terms,
        "headings": headings,
        "key_outputs": assets[:10] if assets else [],
        "evidence_refs": evidence_refs,
        "framework_mentions": frameworks,
        "technical_decisions": decisions,
        "development_challenges": challenges,
        "references_cited": citations,
        "word_count": word_count,
        "word_budget": ch_info.get("word_budget", 0),
        "finalized": ch_info.get("status") == "finalized",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # Save
    brief_path = os.path.join(BRIEFS_DIR, f"{chapter_id}.json")
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)

    return brief


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate Chapter Briefs for cross-session bridging.")
    parser.add_argument("--chapter", default=None,
                        help="Chapter ID to process (e.g. ch3)")
    parser.add_argument("--draft", default=None,
                        help="Explicit draft path (overrides outline)")
    parser.add_argument("--all", action="store_true",
                        help="Process all finalized chapters")
    args = parser.parse_args()

    thesis = load_thesis()
    if not thesis:
        sys.exit(1)

    if not args.chapter and not args.all:
        print("Usage: python generate_chapter_brief.py --chapter ch3")
        print("       python generate_chapter_brief.py --all")
        sys.exit(1)

    processed = []

    if args.chapter:
        ch = find_chapter(thesis, args.chapter)
        if not ch:
            print(f"[error] Chapter '{args.chapter}' not found in outline.")
            sys.exit(1)
        draft_path = args.draft or ch.get("draft_path")
        if not draft_path:
            print(f"[error] No draft_path for {args.chapter}.")
            sys.exit(1)
        text = read_draft(draft_path)
        if not text:
            print(f"[error] Draft not found: {draft_path}")
            sys.exit(1)
        brief = generate_brief_file(args.chapter, text, ch)
        processed.append(brief)
        print(f"[ok] {args.chapter}: {brief['word_count']} words, "
              f"{len(brief['defined_terms'])} terms, "
              f"{len(brief['references_cited'])} citations")

    if args.all:
        for ch in thesis.get("outline", []):
            cid = ch.get("id")
            # Skip if already processed above
            if cid == args.chapter:
                continue
            # Only process drafted or finalized chapters
            if ch.get("status") not in ("drafted", "revised", "finalized"):
                continue
            dp = ch.get("draft_path")
            if not dp:
                continue
            text = read_draft(dp)
            if not text:
                print(f"[warn] {cid}: draft not found ({dp})")
                continue
            brief = generate_brief_file(cid, text, ch)
            processed.append(brief)
            print(f"[ok] {cid}: {brief['word_count']} words, "
                  f"{len(brief['defined_terms'])} terms")

    # Update thesis.json context_bridge
    if processed:
        thesis.setdefault("context_bridge", {})
        existing_briefs = thesis["context_bridge"].get("chapter_briefs_ready", [])
        for b in processed:
            cid = b["chapter_id"]
            if cid not in existing_briefs:
                existing_briefs.append(cid)
        thesis["context_bridge"]["chapter_briefs_ready"] = existing_briefs
        thesis["progress"]["last_updated"] = datetime.now(
            timezone.utc).isoformat(timespec="seconds")
        save_thesis(thesis)
        print(f"\n[ok] Briefs ready: {', '.join(existing_briefs)}")


if __name__ == "__main__":
    main()
