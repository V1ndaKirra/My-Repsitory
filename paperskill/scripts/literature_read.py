# -*- coding: utf-8 -*-
"""On-demand literature query tool for the thesis-writing Agent.

Allows the Agent to read specific sections of a paper during the drafting phase
without loading the entire fulltext into context.

Usage:
  python literature_read.py --key smith2024design
  python literature_read.py --key smith2024design --section results
  python literature_read.py --search "微服务架构" --limit 3
  python literature_read.py --list-index                          # list all indexed papers
  python literature_read.py --key smith2024design --claims         # show key claims only
"""
import json
import os
import re
import sys

ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
META_PATH = os.path.join(ROOT, "library", "metadata.json")
FULLTEXT_DIR = os.path.join(ROOT, "library", "fulltext")
LIT_INDEX_PATH = os.path.join(ROOT, "library", "lit-index.json")


def load_metadata():
    if os.path.exists(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_lit_index():
    if os.path.exists(LIT_INDEX_PATH):
        with open(LIT_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def find_entry(cite_key: str, metadata: list[dict]) -> dict | None:
    for e in metadata:
        if e.get("id") == cite_key:
            return e
    # Try partial match
    for e in metadata:
        if cite_key in (e.get("id") or ""):
            return e
    return None


def read_fulltext(cite_key: str) -> str | None:
    """Read full text from library/fulltext/{cite_key}.txt."""
    path = os.path.join(FULLTEXT_DIR, f"{cite_key}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def read_sections_map(cite_key: str) -> dict | None:
    """Read sections.json for a given cite_key."""
    path = os.path.join(FULLTEXT_DIR, f"{cite_key}.sections.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def extract_section_text(fulltext: str, sections: dict, section_name: str) -> str:
    """Extract text for a named section."""
    if not fulltext or not sections:
        return ""
    sec = sections.get(section_name)
    if not sec:
        # Try partial match
        for k, v in sections.items():
            if k == "full_text_line_count":
                continue
            if section_name in k or k in section_name:
                sec = v
                break
    if not sec:
        return ""

    lines = fulltext.split("\n")
    start = sec.get("start_line", 0)
    end = sec.get("end_line", len(lines))
    return "\n".join(lines[start:end])


def search_fulltext(keyword: str, metadata: list[dict], limit: int = 3) -> list[dict]:
    """Search across all extracted fulltexts for a keyword."""
    results = []
    for entry in metadata:
        cite_key = entry.get("id")
        if not cite_key:
            continue
        text = read_fulltext(cite_key)
        if not text:
            continue
        # Find context around keyword
        matches = list(re.finditer(re.escape(keyword), text, re.IGNORECASE))
        if not matches:
            # Try without escaping
            matches = list(re.finditer(keyword, text, re.IGNORECASE))
        if not matches:
            continue

        snippets = []
        for m in matches[:3]:
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            snippet = text[start:end].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            snippets.append(snippet)

        results.append({
            "cite_key": cite_key,
            "title": entry.get("title", ""),
            "authors": entry.get("authors", []),
            "year": entry.get("year"),
            "match_count": len(matches),
            "snippets": snippets,
        })

        if len(results) >= limit:
            break

    return results


# ── Output formatters ──────────────────────────────────────────

def format_metadata_yaml(entry: dict) -> str:
    """Format a single entry as YAML-like frontmatter."""
    lines = ["---"]
    for field in ["id", "title", "authors", "year", "venue", "doi", "url",
                   "abstract", "language", "extraction_quality",
                   "verification_status", "verified_by", "key_claims"]:
        val = entry.get(field)
        if val:
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            lines.append(f"{field}: {val}")
    lines.append("---")
    return "\n".join(lines)


def cmd_show_entry(args, metadata):
    """Show full metadata + optionally fulltext for a cite-key."""
    entry = find_entry(args.key, metadata)
    if not entry:
        print(f"[error] Entry '{args.key}' not found in library.")
        sys.exit(1)

    print(format_metadata_yaml(entry))
    print()

    if args.claims:
        claims = entry.get("key_claims", [])
        if claims:
            print("## Key Claims\n")
            for i, c in enumerate(claims, 1):
                print(f"{i}. {c}")
            print()
        else:
            print("(no key claims extracted)\n")
        return

    fulltext = read_fulltext(args.key)
    if not fulltext:
        print("[info] No fulltext extracted for this entry.")
        print("  Run literature_extract_fulltext.py first.")
        return

    sections = read_sections_map(args.key) or {}

    if args.section:
        sec_text = extract_section_text(fulltext, sections, args.section)
        if sec_text:
            print(f"## Section: {args.section}\n")
            print(sec_text)
        else:
            available = [k for k in sections if k != "full_text_line_count"]
            print(f"[info] Section '{args.section}' not found.")
            print(f"  Available sections: {', '.join(available)}")
        return

    # Show section listing + abstract
    section_names = [k for k in sections if k != "full_text_line_count"]
    if section_names:
        print(f"## Sections ({len(section_names)})\n")
        for name in section_names:
            sec = sections[name]
            print(f"  [{name}] lines {sec['start_line']}-{sec['end_line']}"
                  + (f" — {sec.get('heading', '')}" if sec.get('heading') else ""))

        # Show abstract if available
        if "abstract" in sections:
            print(f"\n## Abstract\n")
            abstract_text = extract_section_text(fulltext, sections, "abstract")
            if len(abstract_text) > 1200:
                abstract_text = abstract_text[:1200] + "\n... (truncated)"
            print(abstract_text)

    print(f"\n[info] Use --section <name> to read a specific section.")
    print(f"  Use --claims to see key claims only.")


def cmd_search(args, metadata):
    """Search fulltext across all entries."""
    results = search_fulltext(args.search, metadata, args.limit)
    if not results:
        print(f"[info] No results for '{args.search}'")
        return

    print(f"# Search: \"{args.search}\" — {len(results)} result(s)\n")
    for r in results:
        print(f"## [{r['cite_key']}] {r['title']}")
        if r["authors"]:
            print(f"  Authors: {', '.join(r['authors'])}")
        if r["year"]:
            print(f"  Year: {r['year']}")
        print(f"  Matches: {r['match_count']}")
        print()
        for i, snippet in enumerate(r["snippets"], 1):
            print(f"  > ...{snippet}...")
            print()


def cmd_list_index(args, metadata):
    """List all indexed papers with one-liners."""
    lit_index = load_lit_index()
    if lit_index:
        print("# Literature Index\n")
        for item in lit_index:
            cite_key = item.get("cite_key", "?")
            title = item.get("title_zh") or item.get("title", "")
            one_liner = item.get("one_liner", "")
            lang = item.get("language", "")
            ver = item.get("verification_status", "")
            ver_flag = ""
            if ver == "unverifiable":
                ver_flag = " ⚠unverifiable"
            print(f"  [{cite_key}] {title}")
            if one_liner:
                print(f"    {one_liner}")
            if ver_flag:
                print(f"   {ver_flag}")
            print()
    else:
        # Fall back to metadata listing
        print("# Library Entries\n")
        for entry in metadata:
            cite_key = entry.get("id", "?")
            title = entry.get("title", "")[:80]
            authors = entry.get("authors", [])
            author_str = ", ".join(authors[:2]) if authors else ""
            year = entry.get("year", "")
            print(f"  [{cite_key}] {title}")
            print(f"    {author_str} ({year})")
            print()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Query thesis literature library.")
    parser.add_argument("--key", default=None,
                        help="Cite-key to look up")
    parser.add_argument("--section", default=None,
                        help="Read specific section (abstract, introduction, method, ...)")
    parser.add_argument("--claims", action="store_true",
                        help="Show key claims only (no fulltext)")
    parser.add_argument("--search", default=None,
                        help="Search fulltext for keyword")
    parser.add_argument("--list-index", action="store_true",
                        help="List all indexed papers with one-liners")
    parser.add_argument("--limit", type=int, default=3,
                        help="Max search results (default: 3)")
    args = parser.parse_args()

    metadata = load_metadata()

    if args.list_index:
        cmd_list_index(args, metadata)
    elif args.search:
        cmd_search(args, metadata)
    elif args.key:
        cmd_show_entry(args, metadata)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python literature_read.py --key smith2024design")
        print("  python literature_read.py --key smith2024design --section results")
        print("  python literature_read.py --search '微服务架构'")
        print("  python literature_read.py --list-index")


if __name__ == "__main__":
    main()
