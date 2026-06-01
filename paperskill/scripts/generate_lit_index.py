# -*- coding: utf-8 -*-
"""Generate lit-index.json — a compact, searchable literature index.

Reads metadata.json (and optionally fulltext) to produce a structured index
that the Agent loads into context during the drafting phase. Each entry is
compressed to ~200 chars: one-liner summary + key claims + chapter relevance.

Usage:
  python generate_lit_index.py
  python generate_lit_index.py --with-relevance   # also compute chapter relevance
  python generate_lit_index.py --force              # regenerate even if exists
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from thesis_schema import load_thesis_json, save_thesis_json

ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
META_PATH = os.path.join(ROOT, "library", "metadata.json")
INDEX_PATH = os.path.join(ROOT, "library", "lit-index.json")
THESIS_PATH = os.path.join(ROOT, "thesis.json")
FULLTEXT_DIR = os.path.join(ROOT, "library", "fulltext")


def load_metadata() -> list[dict]:
    if not os.path.exists(META_PATH):
        print(f"[error] metadata.json not found at {META_PATH}")
        return []
    with open(META_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_outline() -> list[dict]:
    """Load chapter outline from thesis.json."""
    if not os.path.exists(THESIS_PATH):
        return []
    thesis = load_thesis_json(THESIS_PATH)
    return thesis.get("outline", [])


def load_fulltext(cite_key: str) -> str | None:
    """Try to load fulltext for a cite-key."""
    path = os.path.join(FULLTEXT_DIR, f"{cite_key}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
            if len(text.strip()) > 200:
                return text
    return None


def make_one_liner(entry: dict) -> str:
    """Generate a one-liner summary from available metadata/fulltext."""
    title = entry.get("title", "")
    abstract = entry.get("abstract", "")
    claims = entry.get("key_claims", [])
    has_fulltext = bool(entry.get("full_text_path")) or entry.get("extraction_quality") in {"full", "partial", "ocr"}
    has_verified_abstract = bool(entry.get("abstract_available")) and bool(entry.get("abstract_verified"))

    # Prefer first key claim
    if claims and has_fulltext:
        return claims[0][:200]

    # Use abstract
    if has_verified_abstract and abstract and len(abstract) > 30:
        # Extract first meaningful sentence
        sentences = re.split(r"[。.!！?？\n]", abstract)
        for s in sentences:
            s = s.strip()
            if len(s) > 20:
                return re.sub(r"\s+", " ", s)[:200]
        return abstract[:200]

    # Fallback: use title
    if title:
        if entry.get("language") == "en" and not has_verified_abstract and not has_fulltext:
            return f"{title} [metadata only; abstract unavailable]"
        return title[:200]

    return "(no summary available)"


def get_key_claims(entry: dict, max_claims: int = 3) -> list[str]:
    """Get cleaned key claims."""
    has_fulltext = bool(entry.get("full_text_path")) or entry.get("extraction_quality") in {"full", "partial", "ocr"}
    if not has_fulltext:
        return []
    claims = entry.get("key_claims", [])
    cleaned = []
    for c in claims:
        c = re.sub(r"\s+", " ", str(c)).strip()
        if len(c) > 20 and c not in cleaned:
            cleaned.append(c)
            if len(cleaned) >= max_claims:
                break
    return cleaned


def compute_relevance(entry: dict, outline: list[dict]) -> dict:
    """Simple keyword-based relevance estimation for each chapter.

    Returns {chapter_id: "high"|"medium"|"low"|"none"}.
    Without fulltext or LLM, this is a heuristic based on title/abstract overlap.
    """
    title = (entry.get("title") or "").lower()
    abstract = (entry.get("abstract") or "").lower()
    keywords = [k.lower() for k in entry.get("keywords", [])]
    combined_text = f"{title} {abstract} {' '.join(keywords)}"

    if not outline:
        return {}

    relevance = {}
    for ch in outline:
        ch_id = ch.get("id", "")
        ch_title = (ch.get("title") or "").lower()
        ch_keywords = set()

        # Extract keywords from chapter title and subsection titles
        for word in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z]{3,}", ch_title):
            ch_keywords.add(word)

        for sub in ch.get("subsections", []):
            sub_title = (sub.get("title") or "").lower()
            for word in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z]{3,}", sub_title):
                ch_keywords.add(word)

        # Count keyword overlap
        if not ch_keywords:
            relevance[ch_id] = "low"
            continue

        hits = sum(1 for kw in ch_keywords if kw in combined_text)
        hit_rate = hits / len(ch_keywords) if ch_keywords else 0

        if hit_rate >= 0.3:
            relevance[ch_id] = "high"
        elif hit_rate >= 0.1:
            relevance[ch_id] = "medium"
        elif hits > 0:
            relevance[ch_id] = "low"
        else:
            relevance[ch_id] = "none"

    return relevance


def build_index(metadata: list[dict], outline: list[dict],
                with_relevance: bool = False) -> list[dict]:
    """Build lit-index.json from metadata."""
    index = []

    for entry in metadata:
        cite_key = entry.get("id")
        if not cite_key:
            continue

        title = entry.get("title", "")
        has_fulltext = bool(entry.get("full_text_path") or
                            (os.path.exists(
                                os.path.join(FULLTEXT_DIR, f"{cite_key}.txt"))))

        item = {
            "cite_key": cite_key,
            "title": title,
            "title_zh": entry.get("title_zh", title),
            "authors": entry.get("authors", [])[:3],
            "year": entry.get("year"),
            "venue": entry.get("venue", "")[:60] if entry.get("venue") else None,
            "language": entry.get("language", "en"),
            "one_liner": make_one_liner(entry),
            "key_claims": get_key_claims(entry),
            "has_fulltext": has_fulltext,
            "has_abstract": bool(entry.get("abstract_available")),
            "abstract_source": entry.get("abstract_source", "none"),
            "metadata_only": bool(entry.get("language", "en") == "en" and not entry.get("abstract_available") and not has_fulltext),
            "has_doi": bool(entry.get("doi")),
            "verification_status": entry.get("verification_status", ""),
            "extraction_quality": entry.get("extraction_quality", ""),
        }

        if with_relevance:
            item["relevance"] = compute_relevance(entry, outline)

        index.append(item)

    return index


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate lit-index.json from library metadata.")
    parser.add_argument("--with-relevance", action="store_true",
                        help="Compute chapter relevance scores")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if index exists")
    args = parser.parse_args()

    if os.path.exists(INDEX_PATH) and not args.force:
        print(f"[info] lit-index.json already exists. Use --force to regenerate.")
        return

    metadata = load_metadata()
    if not metadata:
        print("[error] No metadata found. Run literature_search.py first.")
        sys.exit(1)

    outline = load_outline() if args.with_relevance else []
    if args.with_relevance and not outline:
        print("[warn] No outline found in thesis.json. "
              "Relevance scores will be omitted.")

    index = build_index(metadata, outline, with_relevance=args.with_relevance)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # Update thesis.json
    if os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        thesis["context_bridge"]["lit_index_ready"] = True
        thesis["progress"]["last_updated"] = datetime.now(
            timezone.utc).isoformat(timespec="seconds")
        save_thesis_json(THESIS_PATH, thesis)

    print(f"[ok] lit-index.json generated: {len(index)} entries")
    print(f"     with_relevance={args.with_relevance}")


if __name__ == "__main__":
    main()
