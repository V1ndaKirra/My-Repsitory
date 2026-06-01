import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import requests
from thesis_schema import load_thesis_json, save_thesis_json


ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
DEFAULT_KEYWORDS = [k.strip() for k in os.environ.get("THESIS_KEYWORDS", "").split(",") if k.strip()]
META_PATH = os.path.join(ROOT, "library", "metadata.json")
BIB_PATH = os.path.join(ROOT, "library", "references.bib")
THESIS_PATH = os.path.join(ROOT, "thesis.json")


def norm_title(title: str) -> str:
    text = (title or "").lower()
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text)


def clean_text(value: str | None) -> str | None:
    text = (value or "").replace("\u3000", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def normalize_pages(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def join_name_parts(person: dict) -> str | None:
    name = " ".join([x for x in [person.get("given"), person.get("family")] if x]).strip()
    return clean_text(name)


def map_editors(people) -> list[str]:
    editors = []
    for person in people or []:
        if isinstance(person, dict):
            name = join_name_parts(person)
        else:
            name = clean_text(str(person))
        if name:
            editors.append(name)
    return editors


def merge_entry_fields(target: dict, incoming: dict) -> bool:
    changed = False
    for key, value in incoming.items():
        if key in {"id", "added_at"}:
            continue
        if value in (None, "", []):
            continue
        if target.get(key) in (None, "", []):
            target[key] = value
            changed = True
    return changed


def build_key(title: str, authors, year, used_ids) -> str:
    surname = "paper"
    if authors:
        first = authors[0]
        surname = (first.split()[-1] or "paper").lower()
    word = "study"
    words = re.findall(r"[A-Za-z]+", title or "")
    if words:
        word = words[0].lower()
    base = f"{re.sub(r'[^a-z]', '', surname)}{year or 'nd'}{re.sub(r'[^a-z]', '', word)}"
    if not base:
        base = "paperndstudy"
    key = base
    idx = 0
    while key in used_ids:
        idx += 1
        key = f"{base}{chr(96 + idx) if idx <= 26 else idx}"
    used_ids.add(key)
    return key


def map_semantic_scholar(item: dict) -> dict | None:
    title = item.get("title")
    if not title:
        return None
    authors = [a.get("name") for a in (item.get("authors") or []) if a.get("name")]
    doi = (item.get("externalIds") or {}).get("DOI")
    journal_info = item.get("journal") or {}
    abstract = clean_text(item.get("abstract"))
    return {
        "source": "semantic-scholar",
        "type": "journal",
        "title": title,
        "authors": authors,
        "year": item.get("year"),
        "venue": clean_text(item.get("venue") or journal_info.get("name")),
        "doi": doi,
        "url": item.get("url"),
        "abstract": abstract,
        "abstract_available": bool(abstract),
        "abstract_source": "semantic_scholar" if abstract else "none",
        "abstract_verified": bool(abstract),
        "keywords": DEFAULT_KEYWORDS,
        "pdf_path": None,
        "language": "en",
        "volume": clean_text(journal_info.get("volume")),
        "issue": None,
        "pages": normalize_pages(journal_info.get("pages")),
        "publisher": None,
        "pub_place": None,
        "isbn": None,
        "booktitle": None,
        "editors": [],
    }


def map_crossref(item: dict) -> dict | None:
    titles = item.get("title") or []
    title = titles[0] if titles else None
    if not title:
        return None

    authors = []
    for author in item.get("author") or []:
        name = join_name_parts(author)
        if name:
            authors.append(name)

    year = None
    parts = item.get("issued", {}).get("date-parts", [])
    if parts and parts[0]:
        year = parts[0][0]

    doi = item.get("DOI")
    type_raw = (item.get("type") or "").lower()
    ref_type = "journal"
    if "proceedings" in type_raw:
        ref_type = "conference"
    elif "posted-content" in type_raw:
        ref_type = "preprint"
    elif "book" in type_raw:
        ref_type = "book"

    container_title = clean_text((item.get("container-title") or [None])[0])
    event = item.get("event") or {}
    event_name = clean_text(event.get("name"))
    venue = container_title or event_name
    isbn_list = item.get("ISBN") or []

    return {
        "source": "crossref",
        "type": ref_type,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else None,
        "abstract": None,
        "abstract_available": False,
        "abstract_source": "none",
        "abstract_verified": False,
        "keywords": DEFAULT_KEYWORDS,
        "pdf_path": None,
        "language": "en",
        "volume": clean_text(item.get("volume")),
        "issue": clean_text(item.get("issue")),
        "pages": normalize_pages(item.get("page")),
        "publisher": clean_text(item.get("publisher")),
        "pub_place": clean_text(item.get("publisher-location") or event.get("location")),
        "isbn": clean_text(isbn_list[0]) if isbn_list else None,
        "booktitle": venue if ref_type == "conference" else None,
        "editors": map_editors(item.get("editor") or []),
    }


def escape_bib(value: str | None) -> str:
    return (value or "").replace("{", r"\{").replace("}", r"\}")


def main():
    with open(META_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    used_ids = {e.get("id") for e in existing if e.get("id")}
    doi_map = {(e.get("doi") or "").lower(): e for e in existing if e.get("doi")}
    title_map = {norm_title(e.get("title")): e for e in existing if e.get("title")}

    if len(sys.argv) > 1:
        queries = [q.strip() for q in " ".join(sys.argv[1:]).split(",") if q.strip()]
    else:
        queries = os.environ.get("THESIS_SEARCH_QUERIES", "").split(",")
        queries = [q.strip() for q in queries if q.strip()]
    if not queries:
        print("Usage: python literature_search.py 'query1, query2, query3'")
        print("   or: set THESIS_SEARCH_QUERIES env var")
        sys.exit(1)

    candidates = []
    for query in queries:
        try:
            response = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": 8,
                    "fields": "title,authors,year,abstract,venue,journal,externalIds,url",
                },
                timeout=30,
            )
            if response.status_code == 200:
                for item in response.json().get("data", []):
                    mapped = map_semantic_scholar(item)
                    if mapped:
                        candidates.append(mapped)
        except Exception:
            pass

    for query in queries:
        try:
            response = requests.get(
                "https://api.crossref.org/works",
                params={"query": query, "rows": 8},
                headers={"User-Agent": "thesis-agent/1.0 (mailto:thesis@example.com)"},
                timeout=30,
            )
            if response.status_code == 200:
                for item in response.json().get("message", {}).get("items", []):
                    mapped = map_crossref(item)
                    if mapped:
                        candidates.append(mapped)
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_entries = []
    enriched_entries = 0
    for candidate in candidates:
        doi = (candidate.get("doi") or "").lower()
        ntitle = norm_title(candidate.get("title"))
        duplicate = doi_map.get(doi) if doi else None
        if not duplicate:
            duplicate = title_map.get(ntitle)
        if duplicate:
            if merge_entry_fields(duplicate, candidate):
                enriched_entries += 1
            continue
        candidate["id"] = build_key(
            candidate.get("title"),
            candidate.get("authors") or [],
            candidate.get("year"),
            used_ids,
        )
        candidate["added_at"] = now
        new_entries.append(candidate)
        title_map[ntitle] = candidate
        if doi:
            doi_map[doi] = candidate

    all_entries = existing + new_entries
    with open(META_PATH + ".tmp", "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    os.replace(META_PATH + ".tmp", META_PATH)

    type_map = {
        "journal": "article",
        "conference": "inproceedings",
        "thesis": "mastersthesis",
        "book": "book",
        "chapter": "incollection",
        "preprint": "misc",
        "web": "misc",
        "report": "techreport",
    }
    lines = []
    for entry in all_entries:
        bib_type = type_map.get(entry.get("type"), "misc")
        key = entry.get("id") or "ref"
        authors = entry.get("authors") or []
        author_text = " and ".join(authors) if authors else "Unknown"
        lines.append(f"@{bib_type}" + "{" + key + ",")
        lines.append(f"  title = {{{escape_bib(entry.get('title'))}}},")
        lines.append(f"  author = {{{escape_bib(author_text)}}},")
        if entry.get("year"):
            lines.append(f"  year = {{{entry.get('year')}}},")
        if entry.get("type") == "conference":
            if entry.get("booktitle") or entry.get("venue"):
                lines.append(
                    f"  booktitle = {{{escape_bib(entry.get('booktitle') or entry.get('venue'))}}},"
                )
        elif entry.get("venue"):
            lines.append(f"  journal = {{{escape_bib(entry.get('venue'))}}},")
        if entry.get("volume"):
            lines.append(f"  volume = {{{entry.get('volume')}}},")
        if entry.get("issue"):
            lines.append(f"  number = {{{entry.get('issue')}}},")
        if entry.get("pages"):
            lines.append(f"  pages = {{{entry.get('pages')}}},")
        if entry.get("editors"):
            lines.append(f"  editor = {{{escape_bib(' and '.join(entry.get('editors') or []))}}},")
        if entry.get("publisher"):
            lines.append(f"  publisher = {{{escape_bib(entry.get('publisher'))}}},")
        if entry.get("pub_place"):
            lines.append(f"  address = {{{escape_bib(entry.get('pub_place'))}}},")
        if entry.get("isbn"):
            lines.append(f"  isbn = {{{escape_bib(entry.get('isbn'))}}},")
        if entry.get("doi"):
            lines.append(f"  doi = {{{escape_bib(entry.get('doi'))}}},")
        if entry.get("url"):
            lines.append(f"  url = {{{escape_bib(entry.get('url'))}}},")
        lines.append("}")
        lines.append("")
    with open(BIB_PATH + ".tmp", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(BIB_PATH + ".tmp", BIB_PATH)

    thesis = load_thesis_json(THESIS_PATH)
    zh_count = sum(1 for e in all_entries if e.get("language") == "zh")
    en_count = sum(1 for e in all_entries if e.get("language") == "en")
    thesis["library"]["total_count"] = len(all_entries)
    thesis["library"]["chinese_count"] = zh_count
    thesis["library"]["english_count"] = en_count
    if thesis.get("progress", {}).get("phase") in ["init", "outline"]:
        thesis["progress"]["phase"] = "literature"
    thesis["progress"]["last_updated"] = now
    notes = thesis.get("progress", {}).get("notes", [])
    notes.append(
        f"英文文献自动检索完成：新增 {len(new_entries)} 条，补全既有条目 {enriched_entries} 条（Semantic Scholar + CrossRef，已去重）。"
    )
    thesis["progress"]["notes"] = notes
    save_thesis_json(THESIS_PATH, thesis)

    print(len(new_entries))


if __name__ == "__main__":
    main()
