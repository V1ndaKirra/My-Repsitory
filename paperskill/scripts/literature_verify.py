# -*- coding: utf-8 -*-
"""Multi-source cross-validation for library entries without DOI.

For each entry in metadata.json that lacks a DOI:
  1. Search Semantic Scholar by title + first author
  2. Search OpenAlex by title
  3. Search CrossRef by title (exact match)
  4. At least one hit → verification_status: "verified"
  5. None hit → verification_status: "unverifiable"
  6. DOI discovered during verification → auto-fill

Output: updates metadata.json with verification_status, verified_by, verified_doi.

Usage:
  python literature_verify.py
  python literature_verify.py --entry smith2024design   # verify single entry
  python literature_verify.py --unverified-only         # only check unverified
"""
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import requests
from thesis_schema import load_thesis_json, save_thesis_json

ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
META_PATH = os.path.join(ROOT, "library", "metadata.json")
THESIS_PATH = os.path.join(ROOT, "thesis.json")

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_API = "https://api.openalex.org/works"
CROSSREF_API = "https://api.crossref.org/works"

REQUEST_TIMEOUT = 20


def normalize(s: str) -> str:
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s)


def first_author_surname(authors: list[str]) -> str:
    if not authors:
        return ""
    first = authors[0].strip()
    parts = first.split()
    return parts[-1] if parts else first


def verify_semantic_scholar(title: str, author: str) -> dict | None:
    """Search Semantic Scholar. Returns {doi, title} or None."""
    query = title[:200]
    if author:
        query = f"{author} {query}"
    try:
        r = requests.get(
            SEMANTIC_SCHOLAR_API,
            params={"query": query, "limit": 3,
                    "fields": "title,externalIds,authors"},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data", [])
        for item in data:
            item_title = item.get("title", "")
            if normalize(item_title)[:30] == normalize(title)[:30]:
                doi = (item.get("externalIds") or {}).get("DOI")
                return {"doi": doi, "title": item_title}
        # Fuzzy: check first result
        if data:
            item = data[0]
            item_title = item.get("title", "")
            if len(normalize(item_title)) > 10 and normalize(item_title)[:15] == normalize(title)[:15]:
                doi = (item.get("externalIds") or {}).get("DOI")
                return {"doi": doi, "title": item_title}
    except Exception:
        pass
    return None


def verify_openalex(title: str) -> dict | None:
    """Search OpenAlex. Returns {doi, title} or None."""
    try:
        r = requests.get(
            OPENALEX_API,
            params={"search": title[:200], "per_page": 3},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "thesis-agent/1.0 (mailto:thesis@example.com)"},
        )
        if r.status_code != 200:
            return None
        results = r.json().get("results", [])
        for item in results:
            item_title = item.get("title", "")
            if normalize(item_title)[:30] == normalize(title)[:30]:
                doi = item.get("doi", "").replace("https://doi.org/", "")
                return {"doi": doi if doi else None, "title": item_title}
        # Fuzzy
        if results:
            item = results[0]
            item_title = item.get("title", "")
            if len(normalize(item_title)) > 10 and normalize(item_title)[:15] == normalize(title)[:15]:
                doi = item.get("doi", "").replace("https://doi.org/", "")
                return {"doi": doi if doi else None, "title": item_title}
    except Exception:
        pass
    return None


def verify_crossref(title: str) -> dict | None:
    """Search CrossRef by exact title. Returns {doi, title} or None."""
    try:
        r = requests.get(
            CROSSREF_API,
            params={"query.title": title[:200], "rows": 3},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "thesis-agent/1.0 (mailto:thesis@example.com)"},
        )
        if r.status_code != 200:
            return None
        items = r.json().get("message", {}).get("items", [])
        for item in items:
            item_title = (item.get("title") or [None])[0] or ""
            if normalize(item_title)[:30] == normalize(title)[:30]:
                doi = item.get("DOI")
                return {"doi": doi, "title": item_title}
    except Exception:
        pass
    return None


def verify_entry(entry: dict, force: bool = False) -> dict:
    """Verify a single entry. Returns verification result dict."""
    cite_key = entry.get("id", "?")
    title = entry.get("title", "")
    authors = entry.get("authors", [])
    existing_status = entry.get("verification_status")

    # Skip if already verified and not forced
    if existing_status == "verified" and not force:
        return {"cite_key": cite_key, "status": "already_verified"}

    if not title:
        return {"cite_key": cite_key, "status": "no_title"}

    author_surname = first_author_surname(authors)
    verified_by = []
    discovered_doi = None
    discovered_title = None

    # Semantic Scholar
    ss = verify_semantic_scholar(title, author_surname)
    if ss:
        verified_by.append("semantic_scholar")
        if ss.get("doi") and not discovered_doi:
            discovered_doi = ss["doi"]
        discovered_title = ss.get("title") or discovered_title

    # OpenAlex
    oa = verify_openalex(title)
    if oa:
        verified_by.append("openalex")
        if oa.get("doi") and not discovered_doi:
            discovered_doi = oa["doi"]
        discovered_title = oa.get("title") or discovered_title

    # CrossRef
    cr = verify_crossref(title)
    if cr:
        verified_by.append("crossref")
        if cr.get("doi") and not discovered_doi:
            discovered_doi = cr["doi"]
        discovered_title = cr.get("title") or discovered_title

    if verified_by:
        return {
            "cite_key": cite_key,
            "status": "verified",
            "verified_by": verified_by,
            "discovered_doi": discovered_doi,
            "discovered_title": discovered_title,
        }
    else:
        return {
            "cite_key": cite_key,
            "status": "unverifiable",
            "verified_by": [],
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Cross-verify library entries across multiple APIs.")
    parser.add_argument("--entry", default=None,
                        help="Verify a single entry by cite-key")
    parser.add_argument("--unverified-only", action="store_true",
                        help="Only check entries without verification_status")
    parser.add_argument("--force", action="store_true",
                        help="Re-verify even if already verified")
    args = parser.parse_args()

    if not os.path.exists(META_PATH):
        print(f"[error] metadata.json not found at {META_PATH}")
        sys.exit(1)

    with open(META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Filter entries to verify
    if args.entry:
        targets = [e for e in metadata if e.get("id") == args.entry]
        if not targets:
            print(f"[error] Entry '{args.entry}' not found")
            sys.exit(1)
    elif args.unverified_only:
        targets = [e for e in metadata
                   if not e.get("verification_status")
                   or e.get("verification_status") == "unverifiable"]
    else:
        # Only verify English entries without DOI
        targets = [e for e in metadata
                   if e.get("language") == "en" and not e.get("doi")]

    if not targets:
        print("[info] No entries to verify.")
        return

    print(f"[info] Verifying {len(targets)} entry(s) ...\n")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    verified_count = 0
    unverifiable_count = 0
    doi_filled = 0

    for entry in targets:
        cite_key = entry.get("id", "?")
        title = entry.get("title", "")[:80]
        print(f"  [{cite_key}] {title}")

        result = verify_entry(entry, force=args.force)

        if result["status"] == "already_verified":
            print(f"    ↳ already verified")
            continue

        if result["status"] == "verified":
            verified_count += 1
            entry["verification_status"] = "verified"
            entry["verified_by"] = result["verified_by"]
            if result.get("discovered_doi"):
                entry["discovered_doi"] = result["discovered_doi"]
                if not entry.get("doi"):
                    entry["doi"] = result["discovered_doi"]
                    entry["url"] = f"https://doi.org/{result['discovered_doi']}"
                    doi_filled += 1
            entry["verified_at"] = now
            sources = ", ".join(result["verified_by"])
            print(f"    ↳ verified via {sources}"
                  + (f" (DOI: {result['discovered_doi']})" if result.get("discovered_doi") else ""))
        elif result["status"] == "unverifiable":
            unverifiable_count += 1
            entry["verification_status"] = "unverifiable"
            entry["verified_by"] = []
            entry["verified_at"] = now
            print(f"    ↳ UNVERIFIABLE — not found in any source")
        elif result["status"] == "no_title":
            print(f"    ↳ skipped (no title)")
        print()

    # Save
    with open(META_PATH + ".tmp", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    os.replace(META_PATH + ".tmp", META_PATH)

    # Update thesis.json
    if os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        thesis.setdefault("library", {})
        thesis["library"]["verified_count"] = verified_count
        thesis["library"]["unverifiable_count"] = unverifiable_count
        thesis["library"]["doi_filled_count"] = doi_filled
        thesis["progress"]["last_updated"] = now
        save_thesis_json(THESIS_PATH, thesis)

    print(f"[info] Done: {verified_count} verified, "
          f"{unverifiable_count} unverifiable, "
          f"{doi_filled} DOI(s) auto-filled")


if __name__ == "__main__":
    main()
