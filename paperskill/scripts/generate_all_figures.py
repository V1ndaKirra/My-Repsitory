# -*- coding: utf-8 -*-
"""Unified figure generation dispatcher.

Reads project/figures-spec.json and dispatches each diagram job to the
appropriate renderer:
  - Graphviz (flowchart, architecture, er_diagram, module_tree, timeline)
  - Matplotlib (custom figures that need precise pixel control)

This is the single entry point for Phase 5. Agent produces the JSON spec;
this script handles all rendering.

Usage:
  python generate_all_figures.py
  python generate_all_figures.py --theme clean
  python generate_all_figures.py --type flowchart   # only render flowcharts
"""
import json
import os
import sys

ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))
FIG_DIR = os.path.join(ROOT, "assets", "figures")
os.makedirs(FIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(ROOT, "project", "figures-spec.json")


# Types handled by Graphviz
GRAPHVIZ_TYPES = {"flowchart", "architecture", "er_diagram", "module_tree", "timeline"}

# Types handled by matplotlib (custom)
MATPLOTLIB_TYPES = {"custom"}


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate all thesis figures from a JSON spec.")
    parser.add_argument("--theme", default="professional",
                        choices=["professional", "clean"])
    parser.add_argument("--type", default=None,
                        help="Only render figures of this type")
    parser.add_argument("--spec", default=CONFIG_PATH,
                        help="Path to figures-spec.json")
    args = parser.parse_args()

    if not os.path.exists(args.spec):
        print(f"[info] No figures-spec.json found at {args.spec}")
        print("  Agent should create project/figures-spec.json in Phase 5,")
        print("  then re-run this script.")
        return

    with open(args.spec, "r", encoding="utf-8") as f:
        spec_data = json.load(f)

    all_jobs = spec_data.get("figures", spec_data)
    if not isinstance(all_jobs, list):
        print("[error] figures-spec.json must contain a 'figures' list at top level.")
        sys.exit(1)

    # Filter by type if requested
    if args.type:
        all_jobs = [j for j in all_jobs if j.get("type") == args.type]
        if not all_jobs:
            print(f"[info] No figures of type '{args.type}' found.")
            return

    gv_jobs = []
    mpl_jobs = []

    for job in all_jobs:
        jtype = job.get("type", "flowchart")
        if jtype in GRAPHVIZ_TYPES:
            gv_jobs.append(job)
        elif jtype in MATPLOTLIB_TYPES:
            mpl_jobs.append(job)
        else:
            print(f"[warn] Unknown type '{jtype}' for {job.get('id')}, defaulting to Graphviz flowchart")
            job["type"] = "flowchart"
            gv_jobs.append(job)

    total = len(gv_jobs) + len(mpl_jobs)
    print(f"[info] {total} figure(s) to generate "
          f"({len(gv_jobs)} Graphviz, {len(mpl_jobs)} matplotlib)")

    manifest_jobs = []

    # ── Graphviz jobs ──────────────────────────────────────────
    if gv_jobs:
        from generate_dot_diagrams import generate_figure as gv_generate
        for job in gv_jobs:
            out = gv_generate(job, args.theme)
            if out:
                manifest_jobs.append({
                    "id": job["id"],
                    "type": "figure",
                    "caption": job.get("caption", ""),
                    "section_ref": job.get("section_ref", ""),
                    "file": f"assets/figures/{job['id']}.png",
                    "source_format": "graphviz",
                    "size_bytes": os.path.getsize(out),
                })

    # ── Matplotlib jobs (custom) ───────────────────────────────
    if mpl_jobs:
        # Load custom figures module if it exists
        custom_path = os.path.join(ROOT, "project", "custom_figures.py")
        custom_mod = None
        if os.path.exists(custom_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "custom_figures", custom_path)
            custom_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(custom_mod)

        for job in mpl_jobs:
            fn_name = job.get("function", job["id"].replace("-", "_"))
            if custom_mod and hasattr(custom_mod, fn_name):
                out_path = os.path.join(FIG_DIR, f"{job['id']}.png")
                draw_fn = getattr(custom_mod, fn_name)
                draw_fn(out_path)
                size = os.path.getsize(out_path)
                manifest_jobs.append({
                    "id": job["id"],
                    "type": "figure",
                    "caption": job.get("caption", ""),
                    "section_ref": job.get("section_ref", ""),
                    "file": f"assets/figures/{job['id']}.png",
                    "source_format": "matplotlib",
                    "size_bytes": size,
                })
                print(f"[ok] {job['id']} -> {out_path} ({size} bytes)")
            else:
                print(f"[warn] matplotlib function '{fn_name}' not found, "
                      f"skipping {job['id']}")

    # ── Update manifest ────────────────────────────────────────
    if manifest_jobs:
        from assets_generate_figures import update_manifest
        mf_path = update_manifest(manifest_jobs, root=ROOT)
        print(f"[ok] manifest updated: {mf_path}")
    else:
        print("[info] no figures generated")

    print(f"\n[info] Done. {len(manifest_jobs)}/{total} figure(s) generated.")


if __name__ == "__main__":
    main()
