# -*- coding: utf-8 -*-
"""Quick citation validation for a single chapter draft.

Checks that all [@cite-key] references in a markdown file actually exist
in library/metadata.json. Used by the Agent mid-drafting to catch fake
citations before they propagate.

Usage:
  python literature_check_cite.py --draft drafts/01-introduction.md
  python literature_check_cite.py --draft drafts/02-related-work.md --strict
  python literature_check_cite.py --all-drafts   # check all drafts at once
"""
import json
import os
import re
import sys

ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
META_PATH = os.path.join(ROOT, "library", "metadata.json")
DRAFTS_DIR = os.path.join(ROOT, "drafts")


def load_library() -> tuple[set[str], dict]:
    """Load cite-keys and entry metadata from library."""
    if not os.path.exists(META_PATH):
        print("[error] metadata.json not found.", file=sys.stderr)
        return set(), {}

    with open(META_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    valid_keys = set()
    key_map = {}
    for e in entries:
        kid = e.get("id")
        if kid:
            valid_keys.add(kid)
            key_map[kid] = {
                "title": e.get("title", ""),
                "verification_status": e.get("verification_status", ""),
                "doi": e.get("doi"),
                "extraction_quality": e.get("extraction_quality", ""),
            }

    return valid_keys, key_map


def find_citations(text: str) -> list[str]:
    """Extract [@cite-key] patterns from markdown text."""
    keys = []
    for block in re.findall(r"\[@([^\]]+)\]", text):
        for part in block.split(","):
            k = part.strip().lstrip("@").strip()
            if k:
                keys.append(k)
    return keys


def check_draft(draft_path: str, valid_keys: set[str], key_map: dict,
                strict: bool = False) -> list[dict]:
    """Check a single draft. Returns list of issues."""
    issues = []

    if not os.path.exists(draft_path):
        issues.append({
            "level": "error",
            "type": "file_missing",
            "detail": f"Draft file not found: {draft_path}",
        })
        return issues

    with open(draft_path, "r", encoding="utf-8") as f:
        text = f.read()

    citations = find_citations(text)
    unique = sorted(set(citations))

    if not citations:
        issues.append({
            "level": "info",
            "type": "no_citations",
            "detail": "No citations found in this draft.",
        })
        return issues

    for key in unique:
        if key not in valid_keys:
            issues.append({
                "level": "critical",
                "type": "fake_citation",
                "cite_key": key,
                "detail": f"[@{key}] does not exist in library/metadata.json",
                "hint": "Add via literature_search.py or fix cite-key typo.",
            })
        elif strict and key in key_map:
            info = key_map[key]
            if info.get("verification_status") == "unverifiable":
                issues.append({
                    "level": "warning",
                    "type": "unverifiable_citation",
                    "cite_key": key,
                    "detail": f"[@{key}] is marked unverifiable — "
                              f"may be a fabricated or low-quality source.",
                    "hint": "Verify this reference manually or replace with a verified source.",
                })

    return issues


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate citations in thesis drafts.")
    parser.add_argument("--draft", default=None,
                        help="Path to a single draft file to check")
    parser.add_argument("--all-drafts", action="store_true",
                        help="Check all drafts in drafts/")
    parser.add_argument("--strict", action="store_true",
                        help="Also flag unverifiable citations as warnings")
    args = parser.parse_args()

    valid_keys, key_map = load_library()
    if not valid_keys:
        print("[error] No valid cite-keys found in library.", file=sys.stderr)
        print("  Run literature_search.py first.", file=sys.stderr)
        sys.exit(1)

    all_issues = []
    drafts_to_check = []

    if args.draft:
        drafts_to_check = [args.draft]
    elif args.all_drafts:
        if os.path.isdir(DRAFTS_DIR):
            drafts_to_check = sorted([
                os.path.join(DRAFTS_DIR, f)
                for f in os.listdir(DRAFTS_DIR)
                if f.endswith(".md")
            ])
        else:
            print(f"[error] Drafts directory not found: {DRAFTS_DIR}")
            sys.exit(1)
    else:
        print("Usage: python literature_check_cite.py --draft <path>")
        print("       python literature_check_cite.py --all-drafts")
        sys.exit(1)

    for dp in drafts_to_check:
        issues = check_draft(dp, valid_keys, key_map, args.strict)
        for issue in issues:
            issue["file"] = dp
        all_issues.extend(issues)

    # Output
    if not all_issues:
        print("✓ All citations valid.")
        return

    critical = [i for i in all_issues if i["level"] == "critical"]
    warnings = [i for i in all_issues if i["level"] == "warning"]
    infos = [i for i in all_issues if i["level"] == "info"]

    if critical:
        print(f"\n❌ {len(critical)} CRITICAL issue(s):\n")
        for i in critical:
            print(f"  [{i['file']}] {i['detail']}")
            if i.get("hint"):
                print(f"    → {i['hint']}")

    if warnings:
        print(f"\n⚠ {len(warnings)} WARNING(s):\n")
        for i in warnings:
            print(f"  [{i['file']}] {i['detail']}")
            if i.get("hint"):
                print(f"    → {i['hint']}")

    if critical:
        print(f"\n{len(critical)} fake citation(s) detected. Fix before proceeding.")
        sys.exit(1)
    elif warnings:
        print(f"\n{len(warnings)} warning(s). Review before finalizing.")
    else:
        print(f"\n✓ All citations found in library.")


if __name__ == "__main__":
    main()
