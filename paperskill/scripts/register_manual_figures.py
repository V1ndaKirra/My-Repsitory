# -*- coding: utf-8 -*-
"""Register manual screenshots and code captures into assets/manifest.json."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_manifest(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        data = json.load(open(path, "r", encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_metadata(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    try:
        data = json.load(open(path, "r", encoding="utf-8-sig"))
    except Exception:
        return {}

    if isinstance(data, dict):
        return {
            str(name): meta for name, meta in data.items()
            if isinstance(meta, dict)
        }

    if isinstance(data, list):
        result = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("file") or item.get("filename") or item.get("name")
            if name:
                result[str(name)] = item
        return result
    return {}


def infer_caption(name: str) -> str:
    stem = os.path.splitext(name)[0].replace("_", " ").replace("-", " ").strip()
    return f"{stem}截图" if stem else "实现截图"


def normalize_tags(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,，;；]", value) if part.strip()]
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Register manual screenshots/code captures into assets/manifest.json."
    )
    parser.add_argument("--dir", default="assets/screenshots", help="Screenshot directory relative to THESIS_ROOT")
    parser.add_argument("--prefix", default="shot", help="Figure id prefix")
    parser.add_argument("--section", default="5.1 系统实现", help="Default section_ref")
    parser.add_argument("--meta", default="assets/screenshots/metadata.json", help="Optional screenshot metadata json")
    args = parser.parse_args()

    rel_dir = args.dir.replace("/", os.sep)
    abs_dir = os.path.join(ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    supported = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    files = sorted([
        f for f in os.listdir(abs_dir)
        if os.path.splitext(f)[1].lower() in supported
    ])
    if not files:
        print(f"[info] no screenshots found in {abs_dir}")
        return

    metadata = load_metadata(os.path.join(ROOT, args.meta.replace("/", os.sep)))
    manifest_path = os.path.join(ROOT, "assets", "manifest.json")
    existing = load_manifest(manifest_path)
    preserved = [
        a for a in existing
        if not (
            a.get("type") == "figure"
            and str(a.get("file", "")).replace("/", os.sep).startswith(rel_dir)
        )
    ]
    existing_ids = {a.get("id") for a in preserved if a.get("id")}

    registered = []
    counter = 1
    for name in files:
        meta = metadata.get(name, {})
        while f"{args.prefix}-{counter:02d}" in existing_ids:
            counter += 1
        asset_id = f"{args.prefix}-{counter:02d}"
        caption = meta.get("caption") or infer_caption(name)
        section_ref = meta.get("section_ref") or meta.get("section") or args.section
        registered.append({
            "id": asset_id,
            "type": "figure",
            "caption": caption,
            "file": f"{args.dir.rstrip('/')}/{name}",
            "source_format": "manual-screenshot",
            "section_ref": section_ref,
            "module_hint": meta.get("module") or meta.get("module_hint"),
            "proof_note": meta.get("proof") or meta.get("proof_note"),
            "tags": normalize_tags(meta.get("tags", [])),
            "generated_at": now_iso(),
        })
        existing_ids.add(asset_id)
        counter += 1
        print(f"[ok] {asset_id} -> {name}")

    merged = preserved + registered
    json.dump(merged, open(manifest_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[ok] manifest updated: {manifest_path} ({len(registered)} screenshot figure(s))")


if __name__ == "__main__":
    main()
