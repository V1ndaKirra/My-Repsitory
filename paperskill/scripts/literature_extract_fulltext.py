# -*- coding: utf-8 -*-
"""Extract full text from PDFs in library/pdfs/.

For each PDF:
  1. Extract all-page text via pdfplumber (primary) or pypdf (fallback).
  2. If text is extremely sparse AND page count > 5, attempt OCR via Tesseract.
  3. Split extracted text into structured sections (abstract/intro/method/...).
  4. Save full text (library/fulltext/{cite-key}.txt) and section map.
  5. Update metadata.json with full_text_path, extracted_sections, etc.

Matches PDFs to existing library entries by filename → title normalization.
Non-blocking: a PDF that cannot be read is marked extraction_quality:"failed"
rather than crashing the pipeline.

Usage:
  python literature_extract_fulltext.py
  python literature_extract_fulltext.py --force     # re-extract even if already done
  python literature_extract_fulltext.py --pdf library/pdfs/mypaper.pdf  # single PDF
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from thesis_schema import load_thesis_json, save_thesis_json

ROOT = os.environ.get("THESIS_ROOT", os.getcwd())
PDF_DIR = os.path.join(ROOT, "library", "pdfs")
FULLTEXT_DIR = os.path.join(ROOT, "library", "fulltext")
META_PATH = os.path.join(ROOT, "library", "metadata.json")
THESIS_PATH = os.path.join(ROOT, "thesis.json")

os.makedirs(FULLTEXT_DIR, exist_ok=True)

# ── Text extraction backends ───────────────────────────────────

def _pdfplumber_extract(path: str) -> str | None:
    """Extract all text via pdfplumber. Returns None on failure."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return "\n".join(parts) if parts else None
    except Exception:
        return None


def _pypdf_extract(path: str) -> str | None:
    """Extract all text via pypdf. Returns None on failure."""
    try:
        from pypdf import PdfReader
        parts = []
        reader = PdfReader(path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts) if parts else None
    except Exception:
        return None


def _ocr_extract(path: str) -> str | None:
    """OCR the entire PDF via Tesseract. Returns None on failure."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image

        # Check tessdata for Chinese
        import subprocess
        proc = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True, text=True, timeout=10,
        )
        langs = "chi_sim+eng" if "chi_sim" in proc.stdout else "eng"

        images = convert_from_path(path, dpi=200)
        parts = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang=langs)
            if text.strip():
                parts.append(text)
        return "\n".join(parts) if parts else None
    except Exception:
        return None


# ── Section splitting ──────────────────────────────────────────

# Patterns for Chinese academic sections (ordered by specificity)
CN_SECTION_PATTERNS = [
    (r"(?:摘\s*要|abstract|ABSTRACT)", "abstract"),
    (r"(?:关键词|key\s*words|关键字)", "keywords"),
    (r"(?:引言|绪\s*论|前\s*言|引\s*言|introduction|INTRODUCTION)", "introduction"),
    (r"(?:文献综述|相关研究|相关工作|related\s*work|RELATED\s*WORK|literature\s*review)", "related_work"),
    (r"(?:背景|background|BACKGROUND)", "background"),
    (r"(?:方法|研究方法|实验方法|method|METHOD|methodology|METHODOLOGY|approach|APPROACH)", "method"),
    (r"(?:实验|试验|experiment|EXPERIMENT|experiments)", "experiment"),
    (r"(?:结果|result|RESULTS|findings|FINDINGS)", "results"),
    (r"(?:讨论|分析|discussion|DISCUSSION|analysis|ANALYSIS)", "discussion"),
    (r"(?:结论|总结|conclusion|CONCLUSION|summary|SUMMARY)", "conclusion"),
    (r"(?:参考文献|reference|REFERENCES|bibliography|BIBLIOGRAPHY)", "references"),
    (r"(?:致谢|acknowledgement|ACKNOWLEDGEMENT)", "acknowledgement"),
    (r"(?:附录|appendix|APPENDIX)", "appendix"),
]

EN_SECTION_PATTERNS = [
    (r"(?:abstract|ABSTRACT)", "abstract"),
    (r"(?:introduction|INTRODUCTION)", "introduction"),
    (r"(?:related\s*work|RELATED\s*WORK|literature\s*review|LITERATURE\s*REVIEW|background|BACKGROUND)", "related_work"),
    (r"(?:method|METHOD|methodology|METHODOLOGY|approach|APPROACH|design|DESIGN)", "method"),
    (r"(?:experiment|EXPERIMENT|experiments|EXPERIMENTS|evaluation|EVALUATION)", "experiment"),
    (r"(?:result|RESULT|results|RESULTS|findings|FINDINGS)", "results"),
    (r"(?:discussion|DISCUSSION|analysis|ANALYSIS)", "discussion"),
    (r"(?:conclusion|CONCLUSION|summary|SUMMARY|future\s*work)", "conclusion"),
    (r"(?:reference|REFERENCE|references|REFERENCES|bibliography|BIBLIOGRAPHY)", "references"),
    (r"(?:acknowledgement|ACKNOWLEDGEMENT|acknowledgments)", "acknowledgement"),
    (r"(?:appendix|APPENDIX)", "appendix"),
]


def split_sections(text: str) -> dict:
    """Split extracted text into named sections.

    Returns {section_name: {"start_line": N, "end_line": N}, ...}
    and also "full_text_line_count".
    """
    lines = text.split("\n")
    total_lines = len(lines)

    # Try Chinese patterns first (more common in user's use case)
    patterns = CN_SECTION_PATTERNS
    hits = []
    for i, line in enumerate(lines):
        clean = line.strip()
        for pat, name in patterns:
            if re.search(pat, clean):
                hits.append((i, name, clean[:80]))
                break

    # If very few hits, also try English patterns
    if len(hits) < 3:
        for i, line in enumerate(lines):
            clean = line.strip()
            for pat, name in EN_SECTION_PATTERNS:
                if re.search(pat, clean):
                    # Don't duplicate
                    if not any(h[0] == i for h in hits):
                        hits.append((i, name, clean[:80]))
                    break

    # Sort by line number
    hits.sort(key=lambda x: x[0])

    # Build sections
    sections = {}
    for idx, (line_no, name, _heading) in enumerate(hits):
        start = line_no
        end = hits[idx + 1][0] if idx + 1 < len(hits) else total_lines
        sections[name] = {
            "start_line": start,
            "end_line": end,
            "heading": _heading,
        }

    # Always add a "body_top" section (text before first heading)
    if hits:
        first_line = hits[0][0]
        if first_line > 0:
            sections["preamble"] = {
                "start_line": 0,
                "end_line": first_line,
                "heading": "(pre-content)",
            }

    sections["full_text_line_count"] = total_lines
    return sections


# ── Text quality assessment ───────────────────────────────────

def assess_text_quality(text: str, page_count: int) -> str:
    """Determine extraction quality: full | partial | ocr | failed."""
    if not text or not text.strip():
        return "failed"
    lines = [l for l in text.split("\n") if l.strip()]
    char_count = len(text.strip())
    # Rough heuristic: < 30 chars per page on average → very sparse
    if page_count > 0 and char_count / page_count < 30:
        return "failed"
    if char_count < 200:
        return "failed"
    if page_count > 0 and char_count / page_count < 100:
        return "partial"
    return "full"


# ── Key claims extraction ──────────────────────────────────────

def extract_key_claims(text: str, max_claims: int = 5) -> list[str]:
    """Simple heuristic extraction of key claims from conclusion/results sections.
    Looks for sentences containing quantitative claims or strong statements.
    """
    # Try to find conclusion/results sections
    sections = split_sections(text)
    target_sections = ["conclusion", "results", "discussion", "abstract"]

    target_text = ""
    for sec_name in target_sections:
        if sec_name in sections:
            si = sections[sec_name]
            lines = text.split("\n")
            target_text = "\n".join(lines[si["start_line"]:si["end_line"]])
            if len(target_text) > 200:
                break

    if not target_text:
        target_text = text[:3000]

    claims = []
    # Patterns that tend to indicate claims
    patterns = [
        r"(?:结果表明|实验表明|研究发现|结果显[示明]|本文提出|本文实现|本文设计|实验证明)",
        r"(?:result\w*\s+(?:show|indicate|demonstrate|suggest|reveal))",
        r"(?:we\s+(?:propose|present|introduce|develop|demonstrate|show))",
        r"(?:our\s+(?:approach|method|system|framework|model))",
        r"(?:compared\s+(?:to|with))",
        r"(?:outperform|superior|better\s+than|improves?\s+by)",
        r"(?:achieve\w*\s+(?:a|an|the)?\s*\d+)",
        r"\d+%",
    ]

    for pat in patterns:
        for m in re.finditer(pat + r"[^。.!！?\n]{20,200}", target_text, re.IGNORECASE):
            claim = m.group(0).strip()
            claim = re.sub(r"\s+", " ", claim)
            if len(claim) > 30 and claim not in claims:
                claims.append(claim)
                if len(claims) >= max_claims:
                    break
        if len(claims) >= max_claims:
            break

    return claims[:max_claims]


# ── Filename → cite-key matching ───────────────────────────────

def normalize_title(t: str) -> str:
    t = (t or "").lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t)


def match_pdf_to_entry(filename: str, metadata: list[dict]) -> dict | None:
    """Match a PDF filename to an existing metadata entry.
    Returns the entry or None.
    """
    stem = os.path.splitext(filename)[0]
    # Try to recover GBK mojibake
    try:
        stem = stem.encode("cp1252").decode("gbk")
    except Exception:
        pass
    stem_norm = normalize_title(stem)

    # Direct match by title
    for entry in metadata:
        entry_title = normalize_title(entry.get("title", ""))
        if stem_norm and entry_title and (
            stem_norm in entry_title or entry_title in stem_norm or
            stem_norm[:20] == entry_title[:20]
        ):
            return entry

    # Match by PDF path already recorded
    for entry in metadata:
        pdf_path = entry.get("pdf_path", "")
        if pdf_path and filename in pdf_path:
            return entry

    return None


# ── Process single PDF ─────────────────────────────────────────

def process_pdf(pdf_name: str, entry: dict | None, force: bool = False) -> dict:
    """Process a single PDF. Returns a result dict."""
    pdf_path = os.path.join(PDF_DIR, pdf_name)
    result = {
        "pdf_name": pdf_name,
        "cite_key": entry.get("id") if entry else None,
        "status": "pending",
    }

    if not os.path.isfile(pdf_path):
        result["status"] = "not_found"
        return result

    # Count pages
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)
    except Exception:
        page_count = 0

    result["page_count"] = page_count

    # Check if already extracted
    if entry and entry.get("extraction_quality") in ("full", "partial", "ocr") and not force:
        existing_txt = os.path.join(FULLTEXT_DIR, f"{entry['id']}.txt")
        if os.path.exists(existing_txt) and os.path.getsize(existing_txt) > 100:
            result["status"] = "skipped"
            return result

    # Step 1: pdfplumber
    text = _pdfplumber_extract(pdf_path)

    # Step 2: pypdf fallback
    if not text or len(text.strip()) < 200:
        text2 = _pypdf_extract(pdf_path)
        if text2 and len(text2.strip()) > len(text or ""):
            text = text2

    # Step 3: OCR fallback
    quality = assess_text_quality(text or "", page_count)
    if quality == "failed" and page_count > 5:
        ocr_text = _ocr_extract(pdf_path)
        if ocr_text and len(ocr_text.strip()) > 200:
            text = ocr_text
            quality = "ocr"

    # Re-assess after potential OCR
    quality = assess_text_quality(text or "", page_count)
    result["extraction_quality"] = quality
    result["char_count"] = len(text.strip()) if text else 0

    if quality == "failed":
        result["status"] = "failed"
        return result

    # Step 4: Split sections
    sections = split_sections(text)

    # Step 5: Extract key claims
    claims = extract_key_claims(text)

    # Step 6: Determine or create cite_key
    cite_key = entry.get("id") if entry else None
    if not cite_key:
        stem = os.path.splitext(pdf_name)[0]
        try:
            stem = stem.encode("cp1252").decode("gbk")
        except Exception:
            pass
        ascii_part = re.sub(r"[^a-z]", "", stem.lower())
        cite_key = ascii_part if ascii_part else "pdfpaper"
        # Find year from text
        year_match = re.search(r"(20\d{2}|19\d{2})", text[:2000] if text else "")
        year_str = year_match.group(1) if year_match else "nd"
        cite_key = f"{cite_key}{year_str}paper"

    # Step 7: Save outputs
    txt_path = os.path.join(FULLTEXT_DIR, f"{cite_key}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    sections_path = os.path.join(FULLTEXT_DIR, f"{cite_key}.sections.json")
    with open(sections_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    result["status"] = "extracted"
    result["cite_key"] = cite_key
    result["section_count"] = len([k for k in sections if k != "full_text_line_count"])
    result["claim_count"] = len(claims)
    result["claims"] = claims

    # Step 8: Update metadata.json
    if entry:
        entry["full_text_path"] = f"library/fulltext/{cite_key}.txt"
        entry["extracted_sections"] = {k: v for k, v in sections.items()
                                        if k != "full_text_line_count"}
        entry["key_claims"] = claims
        entry["extraction_quality"] = quality
        entry["extraction_page_count"] = page_count
        entry["extracted_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds")

    result["claims"] = claims
    return result


# ── Main ───────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Extract full text from PDFs in library/pdfs/")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if already done")
    parser.add_argument("--pdf", default=None,
                        help="Process a single PDF file (relative to library/pdfs/)")
    parser.add_argument("--max-claims", type=int, default=5,
                        help="Maximum key claims to extract per paper")
    args = parser.parse_args()

    # Load metadata
    metadata = []
    if os.path.exists(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    # Load environment to check OCR availability
    env = {}
    if os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        env = thesis.get("environment", {})

    ocr_available = env.get("ocr_available", False)
    if not ocr_available:
        print("[info] OCR not available (Tesseract not found). "
              "Scanned PDFs will be skipped.")

    # Gather PDFs
    if args.pdf:
        pdf_files = [args.pdf]
    else:
        if not os.path.isdir(PDF_DIR):
            print(f"[info] PDF directory not found: {PDF_DIR}")
            print("  Place PDFs in library/pdfs/ then re-run.")
            return
        pdf_files = sorted([
            f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")
        ])

    if not pdf_files:
        print("[info] No PDF files found in library/pdfs/")
        return

    print(f"[info] Processing {len(pdf_files)} PDF(s) ...\n")

    results = []
    metadata_updated = False

    for pdf_name in pdf_files:
        entry = match_pdf_to_entry(pdf_name, metadata)
        cite_key = entry.get("id") if entry else "?"
        print(f"  [{cite_key}] {pdf_name}")

        result = process_pdf(pdf_name, entry, force=args.force)
        results.append(result)

        status = result["status"]
        if status == "skipped":
            print(f"    ↳ skipped (already extracted)")
        elif status == "extracted":
            quality = result["extraction_quality"]
            chars = result["char_count"]
            secs = result["section_count"]
            claims = result["claim_count"]
            print(f"    ↳ {quality} | {chars} chars | {secs} sections | "
                  f"{claims} claims")
            metadata_updated = True
            # Update entry in metadata if it was matched
            if entry and result["cite_key"]:
                entry["full_text_path"] = f"library/fulltext/{result['cite_key']}.txt"
                entry["extracted_sections"] = True  # detail in sections.json
                entry["key_claims"] = result.get("claims", [])
                entry["extraction_quality"] = quality
                entry["extraction_page_count"] = result.get("page_count", 0)
                entry["extracted_at"] = datetime.now(
                    timezone.utc).isoformat(timespec="seconds")
        elif status == "failed":
            quality = result.get("extraction_quality", "failed")
            pages = result.get("page_count", 0)
            print(f"    ↳ {quality} ({pages} pages, {result.get('char_count', 0)} chars)")
            if entry:
                entry["extraction_quality"] = "failed"
                entry["extraction_page_count"] = pages
                metadata_updated = True
        elif status == "not_found":
            print(f"    ↳ file not found")
        print()

    # Save updated metadata
    if metadata_updated:
        with open(META_PATH + ".tmp", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        os.replace(META_PATH + ".tmp", META_PATH)
        print(f"[ok] metadata.json updated")

    # Update thesis.json
    if os.path.exists(THESIS_PATH):
        thesis = load_thesis_json(THESIS_PATH)
        extracted_count = sum(1 for r in results if r["status"] == "extracted")
        full_count = sum(1 for r in results
                         if r.get("extraction_quality") == "full")
        thesis.setdefault("library", {})
        thesis["library"]["fulltext_count"] = extracted_count
        thesis["library"]["fulltext_full_quality"] = full_count
        thesis["progress"]["last_updated"] = datetime.now(
            timezone.utc).isoformat(timespec="seconds")
        save_thesis_json(THESIS_PATH, thesis)

    # Summary
    extracted = sum(1 for r in results if r["status"] == "extracted")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"[info] Done: {extracted} extracted, {skipped} skipped, "
          f"{failed} failed")


if __name__ == "__main__":
    main()
