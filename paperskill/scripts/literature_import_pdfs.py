import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone

from pypdf import PdfReader
from thesis_schema import load_thesis_json, save_thesis_json


ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
PDF_DIR = os.path.join(ROOT, "library", "pdfs")
META_PATH = os.path.join(ROOT, "library", "metadata.json")
BIB_PATH = os.path.join(ROOT, "library", "references.bib")
THESIS_PATH = os.path.join(ROOT, "thesis.json")


def clean_text(s: str) -> str:
    s = (s or "").replace("\u3000", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def decode_mojibake(name: str) -> str:
    try:
        return name.encode("cp1252").decode("gbk")
    except Exception:
        return name


def key_pinyin_stub(text: str) -> str:
    ascii_part = re.sub(r"[^a-z]", "", text.lower())
    return ascii_part if ascii_part else "cnpaper"


def count_score(entry: dict) -> int:
    score = 0
    for field in ["title", "authors", "year", "venue", "doi", "url", "abstract", "pdf_path"]:
        if entry.get(field):
            score += 1
    if entry.get("abstract"):
        score += min(len(entry["abstract"]) // 200, 3)
    return score


def normalize_title(t: str) -> str:
    t = (t or "").lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t)


def make_id(title: str, year: int | None, used_ids: set[str]) -> str:
    seed = key_pinyin_stub(title)
    base = f"{seed}{year or 'nd'}paper"
    if not base or base == "ndpaper":
        base = "cnpaperndpaper"
    candidate = base
    idx = 0
    while candidate in used_ids:
        idx += 1
        candidate = f"{base}{idx}"
    used_ids.add(candidate)
    return candidate


def extract_pdf_text(path: str, max_pages: int = 2) -> str:
    text_parts = []
    try:
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            text_parts.append(page.extract_text() or "")
    except Exception:
        return ""
    return clean_text("\n".join(text_parts))


def parse_fields(file_name: str, text: str) -> dict:
    stem = os.path.splitext(file_name)[0]
    title_guess = decode_mojibake(stem)
    title_guess = re.sub(r"-[^-]+$", "", title_guess).strip()
    if not title_guess:
        title_guess = stem

    year = None
    m_year = re.search(r"(20\d{2}|19\d{2})", text)
    if m_year:
        year = int(m_year.group(1))

    doi = None
    m_doi = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, flags=re.I)
    if m_doi:
        doi = m_doi.group(0)

    abstract = None
    m_abs = re.search(r"(摘要[:：]?\s*)(.{40,800})", text, flags=re.S)
    if m_abs:
        abstract = clean_text(m_abs.group(2))[:800]

    authors = []
    m_author = re.search(r"-\s*([^-\s]+)$", decode_mojibake(stem))
    if m_author:
        authors = [m_author.group(1)]

    return {
        "title": title_guess,
        "authors": authors,
        "year": year,
        "doi": doi,
        "abstract": abstract,
    }


def bib_type(ref_type: str) -> str:
    mapping = {
        "journal": "article",
        "conference": "inproceedings",
        "thesis": "mastersthesis",
        "book": "book",
        "chapter": "incollection",
        "preprint": "misc",
        "web": "misc",
        "report": "techreport",
    }
    return mapping.get(ref_type, "misc")


def esc(s: str | None) -> str:
    return (s or "").replace("{", r"\{").replace("}", r"\}")


def ensure_json_file(path: str, default_value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_value, f, ensure_ascii=False, indent=2)


def ensure_text_file(path: str, default_value: str = ""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(default_value)


def resolve_import_name(name: str) -> str:
    base, ext = os.path.splitext(name)
    candidate = name
    idx = 1
    while os.path.exists(os.path.join(PDF_DIR, candidate)):
        candidate = f"{base}-{idx}{ext}"
        idx += 1
    return candidate


def import_external_pdfs(source_dir: str) -> tuple[int, list[str]]:
    imported = 0
    imported_names: list[str] = []
    for name in sorted(os.listdir(source_dir)):
        if not name.lower().endswith(".pdf"):
            continue
        src = os.path.join(source_dir, name)
        if not os.path.isfile(src):
            continue
        default_dest = os.path.join(PDF_DIR, name)
        if os.path.abspath(src) == os.path.abspath(default_dest):
            imported_names.append(name)
            continue
        if os.path.exists(default_dest):
            imported_names.append(name)
            continue
        dest_name = resolve_import_name(name)
        dest = os.path.join(PDF_DIR, dest_name)
        shutil.copy2(src, dest)
        imported += 1
        imported_names.append(dest_name)
    return imported, imported_names


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import user-provided Chinese PDFs into library/pdfs and merge metadata."
    )
    parser.add_argument(
        "--dir",
        dest="source_dir",
        help="User-provided directory that already contains downloaded Chinese PDFs.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(PDF_DIR, exist_ok=True)
    ensure_json_file(META_PATH, [])
    ensure_text_file(BIB_PATH)

    with open(META_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)
    if not isinstance(existing, list):
        raise SystemExit(f"[error] metadata must be a list: {META_PATH}")

    imported_count = 0
    source_dir = None
    if args.source_dir:
        source_dir = os.path.abspath(args.source_dir)
        if not os.path.isdir(source_dir):
            raise SystemExit(f"[error] pdf directory not found: {source_dir}")
        imported_count, _ = import_external_pdfs(source_dir)

    used_ids = {e.get("id") for e in existing if e.get("id")}
    existing_by_doi = {(e.get("doi") or "").lower(): e for e in existing if e.get("doi")}
    existing_by_title = {normalize_title(e.get("title")): e for e in existing if e.get("title")}

    files = [name for name in sorted(os.listdir(PDF_DIR)) if name.lower().endswith(".pdf")]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inserted = 0
    merged = 0

    for name in files:
        abs_path = os.path.join(PDF_DIR, name)
        content = extract_pdf_text(abs_path, max_pages=2)
        parsed = parse_fields(name, content)

        entry = {
            "id": None,
            "source": "pdf-only",
            "type": "thesis",
            "title": parsed["title"],
            "authors": parsed["authors"],
            "year": parsed["year"],
            "venue": None,
            "doi": parsed["doi"],
            "url": None,
            "abstract": parsed["abstract"],
            "abstract_available": bool(parsed["abstract"]),
            "abstract_source": "pdf_extract" if parsed["abstract"] else "none",
            "abstract_verified": bool(parsed["abstract"]),
            "keywords": [k.strip() for k in os.environ.get("THESIS_KEYWORDS", "").split(",") if k.strip()],
            "pdf_path": f"library/pdfs/{name}",
            "language": "zh",
            "added_at": now,
        }

        doi_key = (entry.get("doi") or "").lower()
        title_key = normalize_title(entry.get("title"))

        target = None
        if doi_key and doi_key in existing_by_doi:
            target = existing_by_doi[doi_key]
        elif title_key in existing_by_title:
            target = existing_by_title[title_key]

        if target:
            before = count_score(target)
            for k, v in entry.items():
                if k in ["id", "added_at"]:
                    continue
                if (target.get(k) is None or target.get(k) == [] or target.get(k) == "") and v:
                    target[k] = v
            if entry.get("pdf_path"):
                target["pdf_path"] = entry["pdf_path"]
            after = count_score(target)
            if after > before:
                merged += 1
            continue

        entry["id"] = make_id(entry["title"], entry["year"], used_ids)
        existing.append(entry)
        existing_by_title[title_key] = entry
        if doi_key:
            existing_by_doi[doi_key] = entry
        inserted += 1

    with open(META_PATH + ".tmp", "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(META_PATH + ".tmp", META_PATH)

    lines = []
    for e in existing:
        btype = bib_type(e.get("type", "journal"))
        key = e.get("id") or "ref"
        authors = e.get("authors") or []
        author_text = " and ".join(authors) if authors else "Unknown"
        lines.append(f"@{btype}" + "{" + key + ",")
        lines.append(f"  title = {{{esc(e.get('title'))}}},")
        lines.append(f"  author = {{{esc(author_text)}}},")
        if e.get("year"):
            lines.append(f"  year = {{{e.get('year')}}},")
        if e.get("type") == "conference":
            if e.get("booktitle") or e.get("venue"):
                lines.append(f"  booktitle = {{{esc(e.get('booktitle') or e.get('venue'))}}},")
        elif e.get("venue"):
            lines.append(f"  journal = {{{esc(e.get('venue'))}}},")
        if e.get("volume"):
            lines.append(f"  volume = {{{e.get('volume')}}},")
        if e.get("issue"):
            lines.append(f"  number = {{{e.get('issue')}}},")
        if e.get("pages"):
            lines.append(f"  pages = {{{e.get('pages')}}},")
        if e.get("editors"):
            lines.append(f"  editor = {{{esc(' and '.join(e.get('editors') or []))}}},")
        if e.get("publisher"):
            lines.append(f"  publisher = {{{esc(e.get('publisher'))}}},")
        if e.get("pub_place"):
            lines.append(f"  address = {{{esc(e.get('pub_place'))}}},")
        if e.get("isbn"):
            lines.append(f"  isbn = {{{esc(e.get('isbn'))}}},")
        if e.get("doi"):
            lines.append(f"  doi = {{{esc(e.get('doi'))}}},")
        if e.get("url"):
            lines.append(f"  url = {{{esc(e.get('url'))}}},")
        lines.append("}")
        lines.append("")
    with open(BIB_PATH + ".tmp", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(BIB_PATH + ".tmp", BIB_PATH)

    thesis = load_thesis_json(THESIS_PATH)
    zh = sum(1 for e in existing if e.get("language") == "zh")
    en = sum(1 for e in existing if e.get("language") == "en")
    thesis["library"]["total_count"] = len(existing)
    thesis["library"]["chinese_count"] = zh
    thesis["library"]["english_count"] = en
    if source_dir:
        thesis["user_inputs"]["zh_pdf_dir"] = source_dir
        thesis["user_inputs"]["zh_pdf_dir_confirmed"] = True
        thesis["collaboration"]["current_gate"] = "phase-2-literature-imported"
        thesis["collaboration"]["waiting_for_user"] = False
        thesis["collaboration"]["required_user_actions"] = [
            action
            for action in thesis["collaboration"].get("required_user_actions", [])
            if not isinstance(action, dict) or action.get("kind") != "zh-pdf-dir"
        ]
    if thesis.get("progress", {}).get("phase") in ["init", "outline", "comprehension", "literature"]:
        thesis["progress"]["phase"] = "literature"
    thesis["progress"]["last_updated"] = now
    notes = thesis.get("progress", {}).get("notes", [])
    if source_dir:
        notes.append(
            f"用户提供中文 PDF 目录已导入：source={source_dir}，copy={imported_count}，inserted={inserted}，merged={merged}。"
        )
    else:
        notes.append(f"本地中文 PDF 入库完成：inserted={inserted}，merged={merged}。")
    thesis["progress"]["notes"] = notes
    save_thesis_json(THESIS_PATH, thesis)

    print(
        f"files={len(files)}, imported={imported_count}, inserted={inserted}, merged={merged}, total={len(existing)}"
    )


if __name__ == "__main__":
    main()
