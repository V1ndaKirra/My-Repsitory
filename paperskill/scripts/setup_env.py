# -*- coding: utf-8 -*-
"""Phase 0 environment auto-detection and setup.

Checks and optionally installs:
  - Python dependencies (pdfplumber, pypdf, pytesseract, graphviz, etc.)
  - Graphviz `dot` binary (for diagram generation)
  - Tesseract-OCR binary (for scanned PDF OCR fallback)

Download strategy: multi-layer fallback, domestic mirrors prioritized for
users in mainland China.

Usage:
  python setup_env.py              # check only, report status
  python setup_env.py --install    # check + auto-install missing components
  python setup_env.py --status     # print JSON status only
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from thesis_schema import load_thesis_json, save_thesis_json


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))
THESIS_PATH = os.path.join(ROOT, "thesis.json")


# ── PyPI mirrors (domestic priority) ───────────────────────────

PYPI_INDEXES = [
    ("Tsinghua", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("Aliyun",   "https://mirrors.aliyun.com/pypi/simple"),
    ("USTC",     "https://pypi.mirrors.ustc.edu.cn/simple"),
    ("PyPI",     "https://pypi.org/simple"),
]

PYTHON_DEPS = {
    "pdfplumber":  "pdfplumber>=0.10.0",
    "pypdf":       "pypdf>=5.0.0",
    "pytesseract": "pytesseract>=0.3.10",
    "graphviz":    "graphviz>=0.20",
    "pdf2image":   "pdf2image>=1.16.0",
    "Pillow":      "Pillow>=10.0.0",
    "requests":    "requests>=2.28.0",
}


# ── Graphviz download URLs ─────────────────────────────────────

# Graphviz Windows installer (GitLab releases)
# Latest stable: 12.2.1
GRAPHVIZ_VERSION = "12.2.1"
GRAPHVIZ_URLS = [
    # Direct GitLab
    (
        "GitLab Direct",
        f"https://gitlab.com/api/v4/projects/4207231/packages/generic/"
        f"graphviz-releases/{GRAPHVIZ_VERSION}/"
        f"windows_10_cmake_Release_graphviz-install-{GRAPHVIZ_VERSION}-win64.exe",
    ),
    # GHProxy mirrors (for China)
    (
        "gh-proxy.com",
        f"https://gh-proxy.com/"
        f"https://gitlab.com/api/v4/projects/4207231/packages/generic/"
        f"graphviz-releases/{GRAPHVIZ_VERSION}/"
        f"windows_10_cmake_Release_graphviz-install-{GRAPHVIZ_VERSION}-win64.exe",
    ),
]


# ── Tesseract download URLs ────────────────────────────────────

TESSERACT_VERSION = "5.5.0.20241111"
TESSERACT_URLS = [
    (
        "GitHub Releases",
        f"https://github.com/UB-Mannheim/tesseract/releases/download/"
        f"v{TESSERACT_VERSION.split('.2024')[0]}/"
        f"tesseract-ocr-w64-setup-{TESSERACT_VERSION}.exe",
    ),
    (
        "gh-proxy.com",
        f"https://gh-proxy.com/"
        f"https://github.com/UB-Mannheim/tesseract/releases/download/"
        f"v{TESSERACT_VERSION.split('.2024')[0]}/"
        f"tesseract-ocr-w64-setup-{TESSERACT_VERSION}.exe",
    ),
    (
        "gh.api.99988866.xyz",
        f"https://gh.api.99988866.xyz/"
        f"https://github.com/UB-Mannheim/tesseract/releases/download/"
        f"v{TESSERACT_VERSION.split('.2024')[0]}/"
        f"tesseract-ocr-w64-setup-{TESSERACT_VERSION}.exe",
    ),
]

# Additional proxies from env
_extra_proxies = os.environ.get("GH_PROXY_URLS", "").strip()
if _extra_proxies:
    for proxy_url in _extra_proxies.split(","):
        proxy_url = proxy_url.strip()
        if proxy_url:
            TESSERACT_URLS.append((f"custom:{proxy_url}", proxy_url))


# ── Detection helpers ──────────────────────────────────────────

def find_on_path(name: str) -> str | None:
    """Find executable on system PATH."""
    path = shutil.which(name)
    return path if path else None


def find_in_common_dirs(name: str, search_dirs: list[str]) -> str | None:
    """Search for executable in common install directories."""
    for d in search_dirs:
        for root, _, files in os.walk(d):
            if name in files:
                full = os.path.join(root, name)
                if os.path.isfile(full):
                    return full
            # Only search one level deep
            break
    return None


def find_graphviz_dot() -> tuple[str | None, str | None]:
    """Find Graphviz `dot` binary. Returns (path, install_dir)."""
    # 1. PATH
    dot = find_on_path("dot")
    if dot:
        install_dir = os.path.dirname(os.path.dirname(dot))
        return dot, install_dir

    # 2. Common install locations
    candidates = [
        r"C:\Program Files\Graphviz\bin\dot.exe",
        r"C:\Program Files (x86)\Graphviz\bin\dot.exe",
        os.path.expandvars(r"%USERPROFILE%\scoop\apps\graphviz\current\bin\dot.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            install_dir = os.path.dirname(os.path.dirname(c))
            return c, install_dir

    return None, None


def find_tesseract() -> tuple[str | None, str | None]:
    """Find Tesseract-OCR. Returns (tesseract_exe_path, install_dir)."""
    # 1. PATH
    tess = find_on_path("tesseract")
    if tess:
        install_dir = os.path.dirname(tess)
        return tess, install_dir

    # 2. Common install locations
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c, os.path.dirname(c)

    return None, None


# ── Python dependency check & install ──────────────────────────

def check_python_dep(import_name: str) -> bool:
    """Check if a Python package is importable."""
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def install_python_deps(deps: dict[str, str], indexes: list[tuple[str, str]]) -> dict:
    """Install missing Python packages. Returns {pkg: True/False/error}."""
    results = {}
    python_exe = sys.executable

    for import_name, pip_name in deps.items():
        if check_python_dep(import_name):
            results[import_name] = True
            continue

        print(f"  [pip] Installing {pip_name} ...")
        installed = False
        for idx_name, idx_url in indexes:
            try:
                proc = subprocess.run(
                    [python_exe, "-m", "pip", "install", pip_name,
                     "-i", idx_url, "--trusted-host",
                     idx_url.split("://")[1].split("/")[0],
                     "--quiet"],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode == 0 and check_python_dep(import_name):
                    print(f"    ✓ via {idx_name}")
                    results[import_name] = True
                    installed = True
                    break
                else:
                    print(f"    ✗ {idx_name}: {proc.stderr.strip()[:120]}")
            except Exception as e:
                print(f"    ✗ {idx_name}: {e}")

        if not installed:
            results[import_name] = False

    return results


# ── URL check & download ───────────────────────────────────────

def try_url(url: str, timeout: float = 8.0) -> bool:
    """Quickly check if a URL is reachable."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "thesis-setup/1.0")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def download_file(url: str, dest: str, timeout: float = 300.0) -> bool:
    """Download a file with progress indication. Returns True on success."""
    try:
        print(f"    Downloading {os.path.basename(dest)} ...")
        print(f"    From: {url[:100]}...")

        def _report(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                pct = min(int(downloaded / total_size * 100), 100)
                if block_num % 20 == 0:
                    print(f"    {pct}% ({downloaded // 1024 // 1024}MB / "
                          f"{total_size // 1024 // 1024}MB)", end="\r")

        urllib.request.urlretrieve(url, dest, _report)
        print()  # newline after progress
        return os.path.isfile(dest) and os.path.getsize(dest) > 100000
    except Exception as e:
        print(f"\n    Download failed: {e}")
        return False


def download_with_fallbacks(urls: list[tuple[str, str]], dest: str,
                            label: str = "package") -> bool:
    """Try each URL in order until one succeeds."""
    for idx, (url_name, url) in enumerate(urls):
        print(f"  [{label}] Attempting {url_name} ...")
        if idx == 0:
            # For the first URL in the list, do a quick reachability check
            pass  # skip pre-check; just try downloading
        if download_file(url, dest):
            print(f"  [{label}] ✓ Downloaded via {url_name}")
            return True
        # Clean up partial download
        if os.path.exists(dest):
            os.remove(dest)
    return False


# ── Graphviz install ───────────────────────────────────────────

def install_graphviz() -> bool:
    """Download and install Graphviz silently. Returns True on success."""
    print("\n[Graphviz] Not found. Attempting auto-install ...")

    with tempfile.TemporaryDirectory() as tmp:
        installer = os.path.join(tmp, "graphviz-installer.exe")
        success = download_with_fallbacks(GRAPHVIZ_URLS, installer,
                                          label="Graphviz")
        if not success:
            print("[Graphviz] ✗ Download failed from all sources.")
            print("  Manual install: choco install graphviz")
            print("  Or download from: https://graphviz.org/download/")
            return False

        print("[Graphviz] Running installer (silent) ...")
        try:
            proc = subprocess.run(
                [installer, "/S"],
                capture_output=True, text=True, timeout=120,
            )
            # Verify installation
            dot, _ = find_graphviz_dot()
            if dot:
                print(f"[Graphviz] ✓ Installed: {dot}")
                return True
            else:
                print("[Graphviz] ✗ Installer ran but dot not found on PATH.")
                print("  Try adding to PATH manually or reboot.")
                return False
        except Exception as e:
            print(f"[Graphviz] ✗ Install failed: {e}")
            return False


# ── Tesseract install ──────────────────────────────────────────

def install_tesseract() -> bool:
    """Download and install Tesseract-OCR silently. Returns True on success."""
    print("\n[Tesseract] Not found. Attempting auto-install ...")

    with tempfile.TemporaryDirectory() as tmp:
        installer = os.path.join(tmp, "tesseract-installer.exe")
        success = download_with_fallbacks(TESSERACT_URLS, installer,
                                          label="Tesseract")
        if not success:
            print("[Tesseract] ✗ Download failed from all sources.")
            print("  Manual install: choco install tesseract")
            print("  Or download from: https://github.com/UB-Mannheim/tesseract/wiki")
            return False

        print("[Tesseract] Running installer (silent) ...")
        try:
            proc = subprocess.run(
                [installer, "/S"],
                capture_output=True, text=True, timeout=120,
            )
            tess, _ = find_tesseract()
            if tess:
                print(f"[Tesseract] ✓ Installed: {tess}")
                return True
            else:
                print("[Tesseract] ✗ Installer ran but tesseract not found.")
                print("  Check C:\\Program Files\\Tesseract-OCR\\")
                return False
        except Exception as e:
            print(f"[Tesseract] ✗ Install failed: {e}")
            return False


# ── Write to thesis.json ───────────────────────────────────────

def update_thesis_environment(env: dict):
    """Write environment status to thesis.json."""
    if not os.path.exists(THESIS_PATH):
        print(f"[warn] thesis.json not found at {THESIS_PATH}, cannot write environment")
        return

    thesis = load_thesis_json(THESIS_PATH)

    env["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    thesis["environment"] = env

    save_thesis_json(THESIS_PATH, thesis)
    print(f"\n[ok] Environment status written to {THESIS_PATH}")


# ── Main ───────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 0: thesis environment setup and check.")
    parser.add_argument("--install", action="store_true",
                        help="Auto-install missing components")
    parser.add_argument("--status", action="store_true",
                        help="Print JSON status only (quiet mode)")
    parser.add_argument("--skip-graphviz", action="store_true",
                        help="Skip Graphviz setup")
    parser.add_argument("--skip-tesseract", action="store_true",
                        help="Skip Tesseract setup")
    args = parser.parse_args()

    quiet = args.status

    if not quiet:
        print("=" * 60)
        print("  Thesis Writing Skill — Environment Setup")
        print(f"  Workspace: {ROOT}")
        print("=" * 60)

    env_status = {}

    # ── Python dependencies ────────────────────────────────────
    if not quiet:
        print("\n[1/4] Python dependencies ...")

    dep_results = {}
    if args.install:
        dep_results = install_python_deps(PYTHON_DEPS, PYPI_INDEXES)
    else:
        for import_name in PYTHON_DEPS:
            dep_results[import_name] = check_python_dep(import_name)

    all_deps_ok = all(dep_results.values())
    env_status["python_deps"] = dep_results
    env_status["python_deps_ok"] = all_deps_ok

    if not quiet:
        for pkg, ok in dep_results.items():
            status = "✓" if ok else "✗ MISSING"
            print(f"  {status}  {pkg}")
        if not all_deps_ok and not args.install:
            print("  (re-run with --install to auto-install missing deps)")

    # ── Graphviz ────────────────────────────────────────────────
    if not quiet:
        print("\n[2/4] Graphviz (dot binary) ...")

    dot_path, dot_dir = find_graphviz_dot()
    env_status["graphviz_available"] = dot_path is not None
    env_status["graphviz_dot_path"] = dot_path
    env_status["graphviz_install_dir"] = dot_dir

    if not quiet:
        if dot_path:
            print(f"  ✓ Found: {dot_path}")
        elif args.install and not args.skip_graphviz:
            if install_graphviz():
                dot_path, dot_dir = find_graphviz_dot()
                env_status["graphviz_available"] = dot_path is not None
                env_status["graphviz_dot_path"] = dot_path
                env_status["graphviz_install_dir"] = dot_dir
            else:
                print("  ✗ Graphviz not available (diagrams will save .dot only)")
        else:
            print("  ✗ Not found (re-run with --install for auto-setup)")
            print("    Manual: choco install graphviz")

    # ── Tesseract ───────────────────────────────────────────────
    if not quiet:
        print("\n[3/4] Tesseract-OCR ...")

    tess_path, tess_dir = find_tesseract()
    env_status["tesseract_available"] = tess_path is not None
    env_status["tesseract_path"] = tess_path
    env_status["tesseract_install_dir"] = tess_dir
    env_status["ocr_available"] = tess_path is not None

    if not quiet:
        if tess_path:
            print(f"  ✓ Found: {tess_path}")
        elif args.install and not args.skip_tesseract:
            if install_tesseract():
                tess_path, tess_dir = find_tesseract()
                env_status["tesseract_available"] = tess_path is not None
                env_status["tesseract_path"] = tess_path
                env_status["tesseract_install_dir"] = tess_dir
                env_status["ocr_available"] = tess_path is not None
            else:
                print("  ✗ Tesseract not available (scanned PDFs will skip OCR)")
        else:
            print("  ✗ Not found (re-run with --install for auto-setup)")
            print("    Manual: choco install tesseract")

    # ── Other tools ─────────────────────────────────────────────
    if not quiet:
        print("\n[4/4] Other tools ...")

    env_status["pdfplumber_available"] = dep_results.get("pdfplumber", False)
    env_status["pypdf_available"] = dep_results.get("pypdf", False)
    env_status["pillow_available"] = dep_results.get("Pillow", False)
    env_status["graphviz_py_available"] = dep_results.get("graphviz", False)

    if not quiet:
        for key, label in [
            ("pdfplumber_available", "pdfplumber"),
            ("pypdf_available", "pypdf"),
            ("pillow_available", "Pillow"),
            ("graphviz_py_available", "graphviz (Python)"),
        ]:
            status = "✓" if env_status[key] else "✗"
            print(f"  {status}  {label}")

    # ── Write to thesis.json ───────────────────────────────────
    if not quiet:
        print()
    update_thesis_environment(env_status)

    # ── Summary ─────────────────────────────────────────────────
    if quiet:
        print(json.dumps(env_status, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print("  Setup Summary")
        print("=" * 60)
        all_ok = (
            all_deps_ok and
            env_status["graphviz_available"] and
            env_status["tesseract_available"]
        )
        if all_ok:
            print("  ✓ All components ready.")
        else:
            issues = []
            if not all_deps_ok:
                missing = [k for k, v in dep_results.items() if not v]
                issues.append(f"Python deps missing: {', '.join(missing)}")
            if not env_status["graphviz_available"]:
                issues.append("Graphviz not found (diagrams will save .dot only)")
            if not env_status["tesseract_available"]:
                issues.append("Tesseract not found (scanned PDF OCR unavailable)")
            for i in issues:
                print(f"  ! {i}")
            print(f"\n  Fix: re-run with --install to auto-install missing components")
        print()


if __name__ == "__main__":
    main()
