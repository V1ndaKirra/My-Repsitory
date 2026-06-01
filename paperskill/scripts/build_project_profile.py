# -*- coding: utf-8 -*-
r"""Build project/profile.json from a real code repository.

This script is intentionally evidence-first. It extracts what can be observed
from the repository and avoids inventing business responsibilities or tech
selection reasons that are not present in code/config.

Usage:
  python scripts/build_project_profile.py --repo E:\path\to\repo
  python scripts/build_project_profile.py --repo E:\path\to\repo --confirm
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from thesis_schema import load_thesis_json


ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
PROFILE_PATH = os.path.join(ROOT, "project", "profile.json")
THESIS_PATH = os.path.join(ROOT, "thesis.json")

SKIP_DIRS = {
    ".git", ".idea", ".vscode", "node_modules", "dist", "build", "target",
    "coverage", "__pycache__", ".next", ".nuxt", "vendor",
}
SOURCE_EXTS = {".java", ".js", ".ts", ".tsx", ".vue", ".py", ".xml", ".yml", ".yaml", ".sql"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def relpath(path: str, start: str) -> str:
    return os.path.relpath(path, start).replace("\\", "/")


def safe_read(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ""


def walk_files(repo_root: str):
    for current_root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            yield os.path.join(current_root, name)


def parse_pom(pom_path: str) -> dict:
    result = {"path": pom_path, "java_version": None, "spring_boot": None, "dependencies": []}
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
    except Exception:
        return result

    ns_match = re.match(r"\{(.*)\}", root.tag)
    ns = {"m": ns_match.group(1)} if ns_match else {}

    def find_text(xpath: str):
        el = root.find(xpath, ns) if ns else root.find(xpath)
        return el.text.strip() if el is not None and el.text else None

    result["java_version"] = (
        find_text(".//m:properties/m:java.version")
        or find_text(".//m:properties/m:maven.compiler.source")
        or find_text(".//m:properties/m:maven.compiler.target")
    )
    parent_artifact = find_text(".//m:parent/m:artifactId")
    parent_version = find_text(".//m:parent/m:version")
    if parent_artifact and "spring-boot" in parent_artifact:
        result["spring_boot"] = parent_version

    dep_xpath = ".//m:dependency" if ns else ".//dependency"
    for dep in root.findall(dep_xpath, ns) if ns else root.findall(dep_xpath):
        gid = dep.find("m:groupId", ns).text.strip() if ns and dep.find("m:groupId", ns) is not None and dep.find("m:groupId", ns).text else None
        aid = dep.find("m:artifactId", ns).text.strip() if ns and dep.find("m:artifactId", ns) is not None and dep.find("m:artifactId", ns).text else None
        ver = dep.find("m:version", ns).text.strip() if ns and dep.find("m:version", ns) is not None and dep.find("m:version", ns).text else None
        if not ns:
            gid_el = dep.find("groupId")
            aid_el = dep.find("artifactId")
            ver_el = dep.find("version")
            gid = gid or (gid_el.text.strip() if gid_el is not None and gid_el.text else None)
            aid = aid or (aid_el.text.strip() if aid_el is not None and aid_el.text else None)
            ver = ver or (ver_el.text.strip() if ver_el is not None and ver_el.text else None)
        if gid or aid:
            result["dependencies"].append({"groupId": gid, "artifactId": aid, "version": ver})
    return result


def parse_package_json(path: str) -> dict:
    try:
        data = json.loads(safe_read(path) or "{}")
    except Exception:
        data = {}
    deps = {}
    deps.update(data.get("dependencies") or {})
    deps.update(data.get("devDependencies") or {})
    return {
        "path": path,
        "name": data.get("name"),
        "version": data.get("version"),
        "dependencies": deps,
    }


def detect_backend_stack(files: list[str], repo_root: str) -> list[dict]:
    items = []
    pom_files = [p for p in files if os.path.basename(p) == "pom.xml"]
    for pom in pom_files:
        info = parse_pom(pom)
        if info["java_version"]:
            items.append({"name": f"Java {info['java_version']}", "version": info["java_version"], "evidence": [relpath(pom, repo_root)]})
        if info["spring_boot"]:
            items.append({"name": "Spring Boot", "version": info["spring_boot"], "evidence": [relpath(pom, repo_root)]})
        for dep in info["dependencies"]:
            aid = dep.get("artifactId") or ""
            if "mybatis" in aid.lower():
                items.append({"name": aid, "version": dep.get("version"), "evidence": [relpath(pom, repo_root)]})
            if "jjwt" in aid.lower() or "jwt" == aid.lower():
                items.append({"name": "JWT", "version": dep.get("version"), "evidence": [relpath(pom, repo_root)]})
            if "springdoc" in aid.lower() or "swagger" in aid.lower():
                items.append({"name": aid, "version": dep.get("version"), "evidence": [relpath(pom, repo_root)]})
    req_files = [p for p in files if os.path.basename(p) == "requirements.txt"]
    for req in req_files:
        content = safe_read(req)
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pkg = re.split(r"[<>=]", line)[0].strip()
            items.append({"name": pkg, "version": None, "evidence": [relpath(req, repo_root)]})
    if any(p.endswith(".py") for p in files):
        pyproject = next((p for p in files if os.path.basename(p) == "pyproject.toml"), None)
        evidence = [relpath(pyproject, repo_root)] if pyproject else [relpath(next(p for p in files if p.endswith(".py")), repo_root)]
        items.append({"name": "Python", "version": None, "evidence": evidence})
    return dedupe_stack_items(items)


def detect_frontend_stack(files: list[str], repo_root: str) -> list[dict]:
    items = []
    for path in [p for p in files if os.path.basename(p) == "package.json"]:
        info = parse_package_json(path)
        deps = info["dependencies"]
        for name in ("vue", "react", "vite", "element-plus", "pinia", "vue-router", "axios", "echarts", "typescript"):
            if name in deps:
                items.append({"name": name, "version": deps.get(name), "evidence": [relpath(path, repo_root)]})
    return dedupe_stack_items(items)


def detect_database_stack(files: list[str], repo_root: str) -> list[dict]:
    items = []
    for path in files:
        base = os.path.basename(path).lower()
        if base in {"application.yml", "application.yaml", "application.properties"}:
            content = safe_read(path).lower()
            if "mysql" in content:
                items.append({"name": "MySQL", "version": None, "evidence": [relpath(path, repo_root)]})
            if "postgresql" in content or "postgres" in content:
                items.append({"name": "PostgreSQL", "version": None, "evidence": [relpath(path, repo_root)]})
            if "redis" in content:
                items.append({"name": "Redis", "version": None, "evidence": [relpath(path, repo_root)]})
    return dedupe_stack_items(items)


def dedupe_stack_items(items: list[dict]) -> list[dict]:
    merged = {}
    for item in items:
        key = item["name"].lower()
        if key not in merged:
            merged[key] = {"name": item["name"], "version": item.get("version"), "evidence": list(item.get("evidence") or [])}
            continue
        if not merged[key].get("version") and item.get("version"):
            merged[key]["version"] = item["version"]
        for e in item.get("evidence") or []:
            if e not in merged[key]["evidence"]:
                merged[key]["evidence"].append(e)
    return list(merged.values())


def extract_java_controllers(files: list[str], repo_root: str):
    controllers = []
    map_re = re.compile(r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*\(\s*"([^"]*)"')
    req_re = re.compile(r'@RequestMapping\s*\(\s*"([^"]*)"')
    req_named_re = re.compile(r'@RequestMapping\s*\(\s*value\s*=\s*"([^"]*)"')
    class_re = re.compile(r"\bclass\s+([A-Za-z0-9_]+)")
    for path in files:
        if not path.endswith("Controller.java"):
            continue
        text = safe_read(path)
        cls = class_re.search(text)
        class_name = cls.group(1) if cls else os.path.splitext(os.path.basename(path))[0]
        base = ""
        class_part = text[: text.find("class")] if "class" in text else text
        m = req_named_re.search(class_part) or req_re.search(class_part)
        if m:
            base = m.group(1)
        apis = []
        for m in map_re.finditer(text):
            method_name, sub = m.groups()
            http = method_name.replace("Mapping", "").upper()
            sub = sub or ""
            full = normalize_route(base, sub)
            apis.append({"method": http, "path": full, "evidence": relpath(path, repo_root)})
        controllers.append({
            "class_name": class_name,
            "file": relpath(path, repo_root),
            "apis": apis,
        })
    return controllers


def normalize_route(base: str, sub: str) -> str:
    parts = []
    for part in (base or "", sub or ""):
        if not part:
            continue
        part = part.strip()
        if part.startswith("/"):
            part = part[1:]
        if part.endswith("/"):
            part = part[:-1]
        if part:
            parts.append(part)
    return "/" + "/".join(parts) if parts else "/"


def extract_java_entities(files: list[str], repo_root: str):
    entities = []
    class_re = re.compile(r"\bclass\s+([A-Za-z0-9_]+)")
    field_re = re.compile(r"private\s+([A-Za-z0-9_<>, ?]+)\s+([A-Za-z0-9_]+)\s*;")
    for path in files:
        if "/entity/" not in path.replace("\\", "/") and not path.endswith("Entity.java"):
            continue
        text = safe_read(path)
        cls = class_re.search(text)
        if not cls:
            continue
        entity_name = cls.group(1)
        fields = []
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            fm = field_re.search(line)
            if not fm:
                continue
            ftype, fname = fm.groups()
            context = "\n".join(lines[max(0, idx - 2): idx + 1])
            fields.append({
                "name": fname,
                "type": ftype.strip(),
                "pk": "@TableId" in context or fname.lower() == "id",
            })
        entities.append({
            "name": entity_name,
            "table": infer_table_name(text, entity_name),
            "fields": fields[:20],
            "evidence": relpath(path, repo_root),
        })
    return entities


def extract_java_services(files: list[str], repo_root: str):
    services = []
    class_re = re.compile(r"\bclass\s+([A-Za-z0-9_]+)")
    method_re = re.compile(
        r"public\s+(?!class\b)(?!interface\b)([A-Za-z0-9_<>, ?\[\]]+)\s+([A-Za-z0-9_]+)\s*\("
    )
    for path in files:
        normalized = path.replace("\\", "/")
        if "/service/" not in normalized and not path.endswith("Service.java") and not path.endswith("ServiceImpl.java"):
            continue
        text = safe_read(path)
        cls = class_re.search(text)
        if not cls:
            continue
        methods = []
        for m in method_re.finditer(text):
            return_type, name = m.groups()
            if name in {"if", "for", "while", "switch", "catch", "return"}:
                continue
            methods.append({
                "name": name,
                "return_type": return_type.strip(),
            })
        services.append({
            "class_name": cls.group(1),
            "file": relpath(path, repo_root),
            "methods": methods[:20],
            "loc": count_loc(path),
        })
    return services


def infer_table_name(text: str, entity_name: str) -> str:
    m = re.search(r'@TableName\s*\(\s*"([^"]+)"', text)
    if m:
        return m.group(1)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", entity_name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def infer_modules(controllers, services, entities, repo_root: str, files: list[str]):
    entity_names = {e["name"] for e in entities}
    modules = []
    api_counter = 0
    for ctrl in controllers:
        stem = ctrl["class_name"].replace("Controller", "")
        label = humanize_name(stem)
        related_entities = [name for name in entity_names if name.lower().startswith(stem.lower()[:4]) or stem.lower() in name.lower()]
        related_services = [
            svc for svc in services
            if svc["class_name"].lower().startswith(stem.lower())
            or stem.lower() in svc["class_name"].lower()
        ]
        key_files = [ctrl["file"]]
        key_classes = [ctrl["class_name"]]
        for svc in related_services:
            if svc["file"] not in key_files:
                key_files.append(svc["file"])
            if svc["class_name"] not in key_classes:
                key_classes.append(svc["class_name"])
        file_loc = sum(count_loc(os.path.join(repo_root, rel)) for rel in key_files)
        api_counter += len(ctrl["apis"])
        modules.append({
            "id": f"mod-{slugify(stem)}",
            "name": label,
            "responsibility": "Needs confirmation from repo reading or user explanation.",
            "key_classes": key_classes,
            "key_files": key_files[:8],
            "apis": [f"{a['method']} {a['path']}" for a in ctrl["apis"]],
            "entities": related_entities[:5],
            "service_methods": [
                f"{svc['class_name']}.{method['name']}"
                for svc in related_services[:4]
                for method in svc.get("methods", [])[:4]
            ][:10],
            "loc": file_loc,
        })
    matched_service_files = {
        path
        for module in modules
        for path in module.get("key_files", [])
    }
    standalone_services = [
        svc for svc in services
        if svc["file"] not in matched_service_files
    ]
    for svc in standalone_services:
        stem = svc["class_name"].replace("ServiceImpl", "").replace("Service", "")
        label = humanize_name(stem or svc["class_name"])
        modules.append({
            "id": f"mod-{slugify(stem or svc['class_name'])}",
            "name": label,
            "responsibility": "Derived from service layer; refine business responsibility manually.",
            "key_classes": [svc["class_name"]],
            "key_files": [svc["file"]],
            "apis": [],
            "entities": [],
            "service_methods": [
                f"{svc['class_name']}.{method['name']}"
                for method in svc.get("methods", [])[:8]
            ],
            "loc": svc.get("loc", 0),
        })
    if not modules:
        # Fallback: group by top-level source dirs with source files.
        buckets = defaultdict(list)
        for path in files:
            ext = os.path.splitext(path)[1].lower()
            if ext not in SOURCE_EXTS:
                continue
            rel = relpath(path, repo_root)
            parts = rel.split("/")
            key = parts[0] if len(parts) == 1 else parts[-2]
            buckets[key].append(rel)
        for key, rels in sorted(buckets.items()):
            modules.append({
                "id": f"mod-{slugify(key)}",
                "name": humanize_name(key),
                "responsibility": "Derived from source folder grouping; refine manually.",
                "key_classes": [],
                "key_files": rels[:8],
                "apis": [],
                "entities": [],
                "service_methods": [],
                "loc": sum(count_loc(os.path.join(repo_root, p)) for p in rels[:20]),
            })
    return modules, api_counter


def humanize_name(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    s = s.replace("_", " ").replace("-", " ").strip()
    return s[:1].upper() + s[1:] if s else name


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "module"


def count_loc(path: str) -> int:
    text = safe_read(path)
    if not text:
        return 0
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("//") and not stripped.startswith("#") and stripped not in {"{", "}"}:
            count += 1
    return count


def detect_architecture(files: list[str], repo_root: str):
    rels = [relpath(p, repo_root) for p in files]
    layer_counts = {
        "controller": sum(1 for p in rels if p.endswith("Controller.java")),
        "service": sum(1 for p in rels if p.endswith("Service.java") or p.endswith("ServiceImpl.java")),
        "mapper": sum(1 for p in rels if p.endswith("Mapper.java")),
        "entity": sum(1 for p in rels if "/entity/" in p or p.endswith("Entity.java")),
        "frontend_views": sum(1 for p in rels if p.endswith(".vue")),
    }
    style = "mixed"
    if layer_counts["controller"] or layer_counts["service"] or layer_counts["mapper"]:
        style = "layered architecture"
    if layer_counts["frontend_views"] and layer_counts["controller"]:
        style += " with frontend-backend separation"
    return {"style": style, "layer_counts": layer_counts}


def extract_frontend_pages(files: list[str], repo_root: str):
    pages = []
    page_like_exts = {".vue", ".tsx", ".jsx"}
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext not in page_like_exts:
            continue
        rel = relpath(path, repo_root)
        normalized = rel.lower()
        if not any(token in normalized for token in ("/views/", "/pages/", "/src/views/", "/src/pages/")):
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        route_hint = "/" + "/".join(os.path.splitext(rel)[0].split("/")[1:]).lower()
        pages.append({
            "name": humanize_name(stem),
            "file": rel,
            "route_hint": route_hint,
            "loc": count_loc(path),
        })
    return sorted(pages, key=lambda item: item.get("loc", 0), reverse=True)[:80]


def extract_sql_artifacts(files: list[str], repo_root: str):
    artifacts = []
    for path in files:
        if os.path.splitext(path)[1].lower() != ".sql":
            continue
        text = safe_read(path)
        if not text:
            continue
        rel = relpath(path, repo_root)
        tables = []
        for pattern in (
            r"(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?`?([A-Za-z0-9_]+)`?",
            r"(?i)alter\s+table\s+`?([A-Za-z0-9_]+)`?",
            r"(?i)insert\s+into\s+`?([A-Za-z0-9_]+)`?",
        ):
            for match in re.findall(pattern, text):
                if match not in tables:
                    tables.append(match)
        artifacts.append({
            "file": rel,
            "tables": tables[:12],
            "statement_counts": {
                "create_table": len(re.findall(r"(?i)\bcreate\s+table\b", text)),
                "alter_table": len(re.findall(r"(?i)\balter\s+table\b", text)),
                "insert": len(re.findall(r"(?i)\binsert\s+into\b", text)),
                "update": len(re.findall(r"(?i)\bupdate\b", text)),
                "delete": len(re.findall(r"(?i)\bdelete\s+from\b", text)),
                "select": len(re.findall(r"(?i)\bselect\b", text)),
            },
            "loc": count_loc(path),
        })
    return sorted(artifacts, key=lambda item: item.get("loc", 0), reverse=True)[:60]


def extract_config_artifacts(files: list[str], repo_root: str):
    artifacts = []
    interesting_bases = {
        "application.yml", "application.yaml", "application.properties",
        ".env", ".env.development", ".env.production",
    }
    keyword_map = {
        "datasource": "database",
        "mysql": "mysql",
        "redis": "redis",
        "jwt": "jwt",
        "token": "token",
        "upload": "upload",
        "oss": "object-storage",
        "port": "port",
        "security": "security",
        "cors": "cors",
    }
    for path in files:
        base = os.path.basename(path).lower()
        rel = relpath(path, repo_root)
        normalized = rel.lower()
        if base not in interesting_bases and "/config/" not in normalized:
            continue
        text = safe_read(path)
        if not text:
            continue
        lower = text.lower()
        clues = []
        for needle, label in keyword_map.items():
            if needle in lower and label not in clues:
                clues.append(label)
        artifacts.append({
            "file": rel,
            "kind": base or os.path.splitext(base)[1].lstrip("."),
            "clues": clues[:10],
            "loc": count_loc(path),
        })
    return sorted(artifacts, key=lambda item: item.get("loc", 0), reverse=True)[:60]


def build_workload_signals(modules, services, entities, frontend_pages, sql_artifacts, config_artifacts, apis, total_loc):
    return {
        "module_count": len(modules),
        "service_count": len(services),
        "entity_count": len(entities),
        "api_count": len(apis),
        "frontend_page_count": len(frontend_pages),
        "sql_file_count": len(sql_artifacts),
        "config_file_count": len(config_artifacts),
        "total_loc": total_loc,
    }


def extract_issue_markers(files: list[str], repo_root: str):
    markers = []
    pattern = re.compile(r"\b(TODO|FIXME|BUG|HACK|XXX)\b", re.IGNORECASE)
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext not in SOURCE_EXTS:
            continue
        text = safe_read(path)
        if not text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            match = pattern.search(line)
            if not match:
                continue
            snippet = line.strip()
            if len(snippet) > 140:
                snippet = snippet[:137] + "..."
            markers.append({
                "file": relpath(path, repo_root),
                "line": lineno,
                "marker": match.group(1).upper(),
                "snippet": snippet,
            })
            if len(markers) >= 20:
                return markers
    return markers


def observed_file_key(ref: str) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    return text.split(":", 1)[0]


def build_challenge_candidates(profile: dict, issue_markers: list[dict]):
    candidates = []
    seen = set()

    def add_candidate(
        title: str,
        observed_from: list[str],
        category: str,
        focus: str,
        symptom_prompt: str,
        diagnosis_prompt: str,
        fix_prompt: str,
        result_prompt: str,
        defense_angle: str,
        priority: int,
    ):
        key = title.strip().lower()
        if not title or key in seen:
            return
        seen.add(key)
        candidates.append({
            "title": title,
            "status": "candidate",
            "category": category,
            "focus": focus,
            "priority": priority,
            "prompt": f"{symptom_prompt} {diagnosis_prompt} {fix_prompt} {result_prompt}",
            "symptom_prompt": symptom_prompt,
            "diagnosis_prompt": diagnosis_prompt,
            "fix_prompt": fix_prompt,
            "result_prompt": result_prompt,
            "defense_angle": defense_angle,
            "observed_from": [item for item in observed_from if item][:6],
        })

    config_artifacts = profile.get("config_artifacts", [])
    frontend_pages = profile.get("frontend_pages", [])
    sql_artifacts = profile.get("sql_artifacts", [])
    services = profile.get("core_services", [])
    modules = profile.get("modules", [])
    apis = profile.get("apis", {}).get("list", [])

    auth_files = [
        item["file"] for item in config_artifacts
        if any(clue in item.get("clues", []) for clue in ("jwt", "security", "token", "cors"))
    ]
    if auth_files:
        add_candidate(
            "登录认证或权限放行配置",
            auth_files,
            "auth-config",
            "implementation",
            "先回忆问题现象：登录后是否出现过 401、权限不生效、跨域报错或某些接口明明登录了却访问失败。",
            "再写你是如何排查的：检查了哪些放行路径、JWT 配置、过滤器顺序或跨域设置。",
            "接着写你最后改了什么：补放行规则、修正 token 解析、调整拦截配置或统一前后端认证头。",
            "最后写结果：修复后哪些页面或接口恢复正常，截图或运行结果如何证明问题已经解决。",
            "这类问题很适合体现你不仅做了功能，还真正完成了联调和权限调试。",
            78,
        )

    if frontend_pages and (apis or profile.get("tech_stack", {}).get("backend")):
        observed = [page["file"] for page in frontend_pages[:3]]
        observed.extend(api.get("evidence") for api in apis[:2] if api.get("evidence"))
        add_candidate(
            "前后端联调与参数对齐",
            observed,
            "frontend-backend",
            "core_business",
            "先写联调时的具体现象：页面不显示数据、参数提交后无结果、分页筛选异常，或返回字段和页面渲染对不上。",
            "再写排查过程：你如何对照接口文档、控制台请求、后端日志或返回 JSON 定位问题。",
            "接着写修复动作：修改请求参数名、统一返回字段、补充默认值、调整分页条件或修正登录态传递。",
            "最后写修复结果：页面恢复正常后，哪些交互或查询结果已经符合预期。",
            "这类内容很适合证明你做过真实的页面联调，而不是只把前后端代码堆在一起。",
            98,
        )

    if sql_artifacts:
        observed = [item["file"] for item in sql_artifacts[:3]]
        add_candidate(
            "数据库表结构与 SQL 逻辑一致性",
            observed,
            "sql-data",
            "core_business",
            "先写数据库或查询层面的现象：字段对不上、插入失败、更新不生效、查询条件冲突，或分页结果异常。",
            "再写你如何排查：对照表结构、SQL 语句、后端实体字段和实际查询结果逐步定位问题。",
            "接着写你如何修复：调整字段命名、修改 SQL 条件、补字段映射或同步更新表结构与代码。",
            "最后写修复后的结果：增删改查、分页筛选或关联查询恢复正常。",
            "这类问题能很好体现你对数据库、后端逻辑和业务数据流是理解过的。",
            96,
        )

    deploy_files = [
        item["file"] for item in config_artifacts
        if any(clue in item.get("clues", []) for clue in ("database", "mysql", "redis", "port", "object-storage", "upload"))
    ]
    if deploy_files:
        add_candidate(
            "环境配置与本地部署调试",
            deploy_files,
            "environment",
            "supporting",
            "先写环境层面的现象：项目启动失败、数据库连不上、端口冲突、上传路径错误或对象存储配置异常。",
            "再写排查过程：你检查了哪些配置项、启动日志、端口占用情况或本地依赖环境。",
            "接着写修复动作：修改配置文件、补环境变量、调整端口、修正路径或更换本地依赖服务。",
            "最后写修复结果：项目可以稳定启动，相关功能也能正常运行。",
            "这类内容很适合说明你不是只会写代码，也实际把项目跑起来并解决了环境问题。",
            36,
        )

    service_files = [svc["file"] for svc in services[:4]]
    if len(modules) >= 3 or service_files:
        add_candidate(
            "模块职责拆分与业务流程衔接",
            service_files or [item.get("key_files", [""])[0] for item in modules[:3]],
            "module-boundary",
            "implementation",
            "先写实现层面的现象：某些逻辑重复、模块边界不清、流程串起来很绕，或者一个改动会影响多个地方。",
            "再写你如何判断问题根源：通过梳理模块职责、调用链或业务流程发现代码拆分不合理。",
            "接着写你如何调整：重新拆分模块、收敛重复逻辑、把公共流程抽到更合适的位置。",
            "最后写结果：代码结构更清楚，后续功能扩展或问题修改更方便。",
            "这类问题能体现你对项目结构有自己的理解，不只是机械实现功能。",
            90,
        )

    for marker in issue_markers[:3]:
        add_candidate(
            f"代码中标记的 {marker['marker']} 待处理点",
            [f"{marker['file']}:{marker['line']}"],
            "issue-marker",
            "supporting",
            f"先看 `{marker['file']}:{marker['line']}` 附近代码，回忆这里当时暴露出来的具体问题现象是什么。",
            f"再写你当时是如何定位这个问题的，为什么会在这里留下 {marker['marker']} 标记。",
            "接着补充后来是否已经修复；如果修复了，具体改了什么；如果还没修复，计划如何处理。",
            "最后交代当前结果：这个问题是否已经消除，对功能或测试结果有什么影响。",
            "这种候选最适合帮你从真实代码痕迹里回忆开发过程，避免凭空编问题。",
            28,
        )

    if not candidates:
        add_candidate(
            "补充真实开发难点",
            [],
            "manual-recall",
            "core_business",
            "先回忆一个你真正遇到过的现象，比如报错、数据不对、接口不通或页面展示异常。",
            "再按当时的过程写你做了哪些排查，查了哪些日志、请求、配置或数据库内容。",
            "接着写你最后是如何修复的，改了哪些代码、配置或 SQL。",
            "最后写修复后结果如何验证通过。",
            "宁可写一个真实的小问题，也不要编一个很大的假问题。",
            40,
        )

    focus_rank = {"core_business": 0, "implementation": 1, "supporting": 2}
    candidates.sort(
        key=lambda item: (
            focus_rank.get(item.get("focus"), 9),
            -item.get("priority", 0),
            item.get("title", ""),
        )
    )

    filtered = []
    covered_files = set()
    issue_marker_kept = 0
    supporting_kept = 0
    for item in candidates:
        observed_keys = {
            observed_file_key(ref)
            for ref in item.get("observed_from", [])
            if observed_file_key(ref)
        }
        if item.get("focus") == "supporting":
            if supporting_kept >= 1 and len(filtered) >= 4:
                continue
            supporting_kept += 1
        if item.get("category") == "issue-marker":
            if issue_marker_kept >= 1:
                continue
            if observed_keys & covered_files:
                continue
            issue_marker_kept += 1
        filtered.append(item)
        covered_files.update(observed_keys)

    return filtered[:8]


def build_evidence_index(profile: dict) -> list[dict]:
    evidence = []
    for item in profile.get("tech_stack", {}).get("backend", []):
        evidence.append({"path": f"tech_stack.backend.{slugify(item['name'])}", "evidence": item.get("evidence", [])})
    for item in profile.get("tech_stack", {}).get("frontend", []):
        evidence.append({"path": f"tech_stack.frontend.{slugify(item['name'])}", "evidence": item.get("evidence", [])})
    for item in profile.get("tech_stack", {}).get("database", []):
        evidence.append({"path": f"tech_stack.database.{slugify(item['name'])}", "evidence": item.get("evidence", [])})
    for module in profile.get("modules", []):
        evidence.append({"path": f"modules.{slugify(module['name'])}", "evidence": module.get("key_files", [])})
    for service in profile.get("core_services", []):
        evidence.append({"path": f"core_services.{slugify(service['class_name'])}", "evidence": [service.get("file")]})
    for entity in profile.get("data_model", {}).get("entities", []):
        evidence.append({"path": f"data_model.entities.{entity['name']}", "evidence": [entity.get("evidence")]})
    for api in profile.get("apis", {}).get("list", [])[:200]:
        evidence.append({"path": f"apis.{api['method'].lower()}_{slugify(api['path'])}", "evidence": [api.get("evidence")]})
    for page in profile.get("frontend_pages", []):
        evidence.append({"path": f"frontend_pages.{slugify(page['name'])}", "evidence": [page.get("file")]})
    for artifact in profile.get("sql_artifacts", []):
        evidence.append({"path": f"sql_artifacts.{slugify(artifact['file'])}", "evidence": [artifact.get("file")]})
    for artifact in profile.get("config_artifacts", []):
        evidence.append({"path": f"config_artifacts.{slugify(artifact['file'])}", "evidence": [artifact.get("file")]})
    return evidence


def build_profile(repo_root: str) -> dict:
    files = list(walk_files(repo_root))
    source_files = [p for p in files if os.path.splitext(p)[1].lower() in SOURCE_EXTS]
    controllers = extract_java_controllers(source_files, repo_root)
    entities = extract_java_entities(source_files, repo_root)
    services = extract_java_services(source_files, repo_root)
    modules, api_total = infer_modules(controllers, services, entities, repo_root, source_files)
    apis = [api for ctrl in controllers for api in ctrl["apis"]]
    by_method = Counter(a["method"] for a in apis)
    backend = detect_backend_stack(files, repo_root)
    frontend = detect_frontend_stack(files, repo_root)
    database = detect_database_stack(files, repo_root)
    architecture = detect_architecture(source_files, repo_root)
    frontend_pages = extract_frontend_pages(source_files, repo_root)
    sql_artifacts = extract_sql_artifacts(source_files, repo_root)
    config_artifacts = extract_config_artifacts(files, repo_root)
    issue_markers = extract_issue_markers(source_files, repo_root)
    total_loc = sum(count_loc(p) for p in source_files)

    profile = {
        "status": "draft",
        "repo_root": repo_root.replace("\\", "/"),
        "scanned_at": now_iso(),
        "comprehension_depth": "basic",
        "depth_coverage": {
            "has_tech_stack": bool(backend or frontend or database),
            "has_architecture": bool(architecture),
            "has_modules": bool(modules),
            "has_data_model": bool(entities),
            "has_apis": bool(apis),
            "has_core_services": bool(services),
            "has_frontend_pages": bool(frontend_pages),
            "has_sql_artifacts": bool(sql_artifacts),
            "has_config_artifacts": bool(config_artifacts),
        },
        "tech_stack": {
            "backend": backend,
            "frontend": frontend,
            "database": database,
        },
        "architecture": architecture,
        "modules": modules,
        "data_model": {
            "entities": entities,
            "relation_summary": "Needs manual refinement from ER or schema review." if entities else "",
        },
        "apis": {
            "total": api_total or len(apis),
            "by_method": dict(by_method),
            "list": apis[:200],
        },
        "core_services": services[:80],
        "frontend_pages": frontend_pages,
        "sql_artifacts": sql_artifacts,
        "config_artifacts": config_artifacts,
        "issue_markers": issue_markers,
        "scale": {
            "total_loc": total_loc,
            "source_file_count": len(source_files),
        },
        "workload_signals": build_workload_signals(
            modules, services, entities, frontend_pages, sql_artifacts, config_artifacts, apis, total_loc
        ),
        "tech_decisions": [
            {
                "topic": item["name"],
                "status": "needs-user-confirmation",
                "observed_from": item.get("evidence", []),
                "suggested_prompt": f"Explain why {item['name']} was chosen for this project.",
            }
            for item in (backend + frontend + database)[:12]
        ],
        "implementation_highlights": [
            {
                "module": module["name"],
                "evidence": module.get("key_files", [])[:3],
                "apis": module.get("apis", [])[:5],
                "service_methods": module.get("service_methods", [])[:5],
                "frontend_pages": [
                    page.get("file")
                    for page in frontend_pages
                    if slugify(module["name"]) in slugify(page.get("file", ""))
                ][:3],
            }
            for module in sorted(modules, key=lambda m: m.get("loc", 0), reverse=True)[:8]
        ],
        "challenge_log": [],
        "evidence_index": [],
    }
    profile["challenge_log"] = build_challenge_candidates(profile, issue_markers)
    profile["evidence_index"] = build_evidence_index(profile)
    return profile


def write_profile(profile: dict):
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def update_thesis(repo_root: str, confirm: bool):
    if not os.path.exists(THESIS_PATH):
        return
    try:
        thesis = load_thesis_json(THESIS_PATH)
    except Exception:
        return
    thesis.setdefault("project", {})
    thesis["project"]["status"] = "confirmed" if confirm else "draft"
    thesis["project"]["profile_path"] = "project/profile.json"
    thesis["project"]["repo_root"] = repo_root.replace("\\", "/")
    thesis.setdefault("progress", {})
    thesis["progress"]["last_updated"] = now_iso()
    notes = thesis["progress"].get("notes", [])
    notes.append(f"项目画像已从仓库扫描生成：{repo_root}")
    thesis["progress"]["notes"] = notes[-20:]
    with open(THESIS_PATH, "w", encoding="utf-8") as f:
        json.dump(thesis, f, ensure_ascii=False, indent=2)


def resolve_repo(args_repo: str | None) -> str:
    if args_repo:
        return os.path.abspath(args_repo)
    if os.path.exists(THESIS_PATH):
        try:
            thesis = load_thesis_json(THESIS_PATH)
            repo = thesis.get("project", {}).get("repo_root")
            if repo:
                return os.path.abspath(repo)
        except Exception:
            pass
    raise SystemExit("[error] Please provide --repo or set thesis.json.project.repo_root first.")


def main():
    parser = argparse.ArgumentParser(description="Build project/profile.json from a real repository.")
    parser.add_argument("--repo", default=None, help="Repository root to scan")
    parser.add_argument("--confirm", action="store_true", help="Mark thesis.json.project.status as confirmed")
    args = parser.parse_args()

    repo_root = resolve_repo(args.repo)
    if not os.path.isdir(repo_root):
        raise SystemExit(f"[error] repo not found: {repo_root}")

    profile = build_profile(repo_root)
    write_profile(profile)
    update_thesis(repo_root, args.confirm)

    print(f"[ok] profile written: {PROFILE_PATH}")
    print(json.dumps({
        "repo_root": profile["repo_root"],
        "modules": len(profile["modules"]),
        "apis": profile["apis"]["total"],
        "entities": len(profile["data_model"]["entities"]),
        "source_file_count": profile["scale"]["source_file_count"],
        "total_loc": profile["scale"]["total_loc"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
