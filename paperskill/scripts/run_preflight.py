import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from thesis_schema import load_thesis_json


ROOT = os.environ.get("THESIS_ROOT", os.getcwd())


def read_json(path):
    if os.path.abspath(path) == os.path.abspath(os.path.join(ROOT, "thesis.json")):
        return load_thesis_json(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def find_citations(text):
    keys = []
    for block in re.findall(r"\[@([^\]]+)\]", text):
        for part in block.split(","):
            k = part.strip().lstrip("@")
            if k:
                keys.append(k)
    return keys


def find_todos(text):
    return re.findall(r"\[TODO:[^\]]+\]", text)


def find_evidence_refs(text):
    return [m.strip().strip('"').strip("'")
            for m in re.findall(r"(?im)^\s*path:\s*([^\n]+)", text)]


def has_selection_rationale(text):
    return bool(
        re.search(r"(选用|采用|选择|技术选型|框架选型|数据库选型)", text)
        and re.search(r"(因为|原因|考虑到|适合|便于|优势|优点|为了|满足)", text)
    )


def has_challenge_solution_narrative(text):
    has_challenge = re.search(r"(难点|问题|瓶颈|报错|冲突|卡顿|失败|兼容性|性能问题)", text)
    has_solution = re.search(r"(解决|处理|优化|修复|改为|通过|排查|最终采用)", text)
    return bool(has_challenge and has_solution)


def get_degree_policy(thesis):
    degree = (
        thesis.get("meta", {}).get("degree_level")
        or thesis.get("meta", {}).get("degree")
        or "undergrad"
    )
    degree = str(degree).lower()
    if degree in {"master", "masters", "graduate"}:
        return {
            "degree": "master",
            "intro_cites_min": 5,
            "related_cites_min": 2,
            "english_ratio_min": 0.4,
            "total_refs_min": 25,
            "implementation_evidence_min": 2,
        }
    if degree in {"phd", "doctor", "doctoral"}:
        return {
            "degree": "phd",
            "intro_cites_min": 8,
            "related_cites_min": 3,
            "english_ratio_min": 0.5,
            "total_refs_min": 35,
            "implementation_evidence_min": 2,
        }
    return {
        "degree": "undergrad",
        "intro_cites_min": 3,
        "related_cites_min": 1,
        "english_ratio_min": 0.2,
        "total_refs_min": 15,
        "implementation_evidence_min": 3,
    }


def count_ai_sounding_phrases(text):
    phrases = [
        "随着时代的发展",
        "随着信息化时代的到来",
        "在当今社会",
        "众所周知",
        "具有重要的理论意义",
        "具有重要现实意义",
        "具有较高的研究价值",
        "在一定程度上",
        "本文旨在",
        "综上所述可知",
        "由此可见",
        "值得注意的是",
        "不难看出",
    ]
    count = 0
    hits = []
    for p in phrases:
        if p in text:
            count += text.count(p)
            hits.append(p)
    return count, hits


def strip_asset_refs(text):
    text = re.sub(r"\{\{(?:fig|tab|eq):[^}]+\}\}", "", text)
    text = re.sub(r"\[@[^\]]+\]", "", text)
    return text


def has_natural_screenshot_context(paragraph):
    compact = re.sub(r"\s+", "", paragraph)
    if not compact:
        return False
    context_markers = [
        "如图", "所示", "可以看出", "页面", "界面", "代码", "配置", "运行结果",
        "登录", "查询", "模块", "功能", "用于", "实现", "展示", "说明", "验证",
        "修改后", "修复后", "报错", "结果",
    ]
    if any(marker in compact for marker in context_markers):
        return True
    stripped = re.sub(r"[，。；：、“”‘’（）()《》【】\-\s]", "", strip_asset_refs(paragraph))
    return len(stripped) >= 20


def is_generic_screenshot_caption(caption):
    caption = str(caption or "").strip().lower()
    if not caption:
        return True
    if caption in {"截图", "页面截图", "代码截图", "运行结果截图", "界面截图", "image", "screenshot"}:
        return True
    stem = re.sub(r"(截图|页面|代码|运行结果|界面|结果|\s|-|_)", "", caption)
    return len(stem) <= 2


def screenshot_usage_phase(asset):
    hints = " ".join(
        [
            str(asset.get("caption", "")),
            str(asset.get("proof_note", "")),
            str(asset.get("section_ref", "")),
            str(asset.get("module_hint", "")),
            " ".join(asset.get("tags", []) if isinstance(asset.get("tags"), list) else [str(asset.get("tags", ""))]),
        ]
    )
    normalized = re.sub(r"\s+", "", hints).lower()
    if any(
        flag in normalized
        for flag in (
            "鎶ラ敊",
            "寮傚父",
            "閿欒",
            "澶辫触",
            "淇",
            "鎺掓煡",
            "鏃ュ織",
            "娴嬭瘯",
            "杩愯缁撴灉",
            "error",
            "debug",
            "log",
            "fix",
            "trace",
        )
    ):
        return "debugging"
    return "implementation"


def count_words(text):
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"[A-Za-z]+", text))
    return chinese + english * 2


def figure_asset_ready_for_docx(asset):
    render_path = str(asset.get("render_file") or "").strip()
    file_path = str(asset.get("file") or "").strip()
    candidate = render_path or file_path
    ext = os.path.splitext(candidate)[1].lower()
    return bool(candidate) and ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif"} and asset.get("ready_for_docx", True) is not False


def add_issue(issues, check_id, level, title, location, detail, fix_hint):
    issues.append(
        {
            "check_id": check_id,
            "level": level,
            "title": title,
            "location": location,
            "detail": detail,
            "fix_hint": fix_hint,
        }
    )


def format_required_actions(actions):
    result = []
    for action in actions or []:
        if isinstance(action, str):
            if action.strip():
                result.append(action.strip())
            continue
        if not isinstance(action, dict):
            continue
        title = str(action.get("title") or action.get("kind") or "user-action").strip()
        done_when = str(action.get("done_when") or "").strip()
        if done_when:
            result.append(f"{title} -> {done_when}")
        else:
            result.append(title)
    return result


def missing_journal_detail_fields(entry):
    missing = []
    for field in ["volume", "issue", "pages"]:
        if not entry.get(field):
            missing.append(field)
    return missing


def missing_conference_detail_fields(entry):
    missing = []
    for field in ["booktitle", "pub_place", "publisher", "pages"]:
        if not entry.get(field):
            missing.append(field)
    if entry.get("isbn") and not entry.get("editors"):
        missing.append("editors")
    return missing


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    thesis = read_json(os.path.join(ROOT, "thesis.json"))
    policy = get_degree_policy(thesis)
    contract = read_json(os.path.join(ROOT, "template", "format-contract.json"))
    profile = read_json(os.path.join(ROOT, "project", "profile.json"))
    library = read_json(os.path.join(ROOT, "library", "metadata.json"))
    assets = read_json(os.path.join(ROOT, "assets", "manifest.json"))

    lib_map = {e.get("id"): e for e in library if e.get("id")}
    asset_ids = {a.get("id") for a in assets if a.get("id")}
    section_ids = set()
    for ch in thesis.get("outline", []):
        section_ids.add(ch.get("id"))
        for sec in ch.get("subsections", []):
            section_ids.add(sec.get("id"))

    issues = []
    used_cites = []
    used_assets = []
    collaboration = thesis.get("collaboration", {})
    user_inputs = thesis.get("user_inputs", {})

    if collaboration.get("waiting_for_user"):
        action_lines = format_required_actions(collaboration.get("required_user_actions", []))
        add_issue(
            issues,
            "C-13",
            "critical",
            "当前工作区仍在等待用户确认或补充材料",
            "thesis.json:collaboration",
            (
                "协作状态仍为 waiting_for_user=true。"
                + (f" 待完成事项: {'; '.join(action_lines)}。" if action_lines else "")
            ),
            "先向用户汇报已完成内容、产物路径和待补材料，等用户确认后再继续后续写作或排版。",
        )

    if thesis.get("project", {}).get("status") == "confirmed" and not user_inputs.get("repo_root_confirmed"):
        add_issue(
            issues,
            "H-16",
            "high",
            "项目路径尚未由用户确认",
            "thesis.json:user_inputs.repo_root_confirmed",
            "项目画像已经进入 confirmed，但没有记录用户确认过 repo_root，后续证据链可能建立在错误项目上。",
            "先让用户明确确认项目目录，并把 thesis.json.user_inputs.repo_root_confirmed 设为 true。",
        )

    if thesis.get("library", {}).get("chinese_count", 0) > 0 and not user_inputs.get("zh_pdf_dir_confirmed"):
        add_issue(
            issues,
            "H-17",
            "high",
            "中文文献目录尚未由用户确认",
            "thesis.json:user_inputs.zh_pdf_dir_confirmed",
            "工作区已经存在中文文献，但没有记录用户提供的下载目录，来源链条不完整。",
            "请用户提供中文 PDF 下载目录，并通过 literature_import_pdfs.py --dir <目录> 导入后再继续。",
        )

    # Load drafts
    drafts = {}
    missing_drafts = []
    for ch in thesis.get("outline", []):
        p = ch.get("draft_path")
        if not p:
            continue
        ap = os.path.join(ROOT, p.replace("/", os.sep))
        if os.path.exists(ap):
            drafts[p] = read_text(ap)
        else:
            missing_drafts.append(p)

    if drafts.get("drafts/05-implementation.md", "") and not user_inputs.get("screenshot_dir_confirmed"):
        add_issue(
            issues,
            "M-16",
            "medium",
            "实现章节截图目录尚未由用户确认",
            "thesis.json:user_inputs.screenshot_dir_confirmed",
            "系统实现章节已经开始写作，但还没有确认用户用于上传页面、代码、配置和运行结果截图的目录。",
            "先确认截图目录，等用户补充截图并登记后，再继续扩写系统实现过程。",
        )

    # C-06 draft existence/status
    required_ids = {"ch0", "ch3", "ch4", "ch5", "ch6", "ch7"}
    id_to_ch = {c.get("id"): c for c in thesis.get("outline", [])}
    for cid in required_ids:
        ch = id_to_ch.get(cid)
        if not ch:
            add_issue(
                issues,
                "C-06",
                "critical",
                "章节未在大纲中声明",
                "thesis.json:outline",
                f"缺少必需章节 {cid}。",
                "在 thesis.json outline 中补齐章节定义（thesis-orchestrator）。",
            )
            continue
        p = ch.get("draft_path")
        if p not in drafts:
            add_issue(
                issues,
                "C-06",
                "critical",
                "必需章节草稿缺失",
                p or "thesis.json:outline",
                f"{cid} 的草稿文件不存在。",
                "先生成对应 drafts 文件（academic-drafting）。",
            )
        if ch.get("status") not in {"drafted", "revised", "finalized"}:
            add_issue(
                issues,
                "C-06",
                "critical",
                "必需章节状态未达 drafted",
                f"thesis.json:outline:{cid}",
                f"{cid} 当前状态为 {ch.get('status')}。",
                "将章节补全并更新状态到 drafted（academic-drafting + orchestrator）。",
            )

    # C-07 contract
    if contract.get("status") != "confirmed":
        add_issue(
            issues,
            "C-07",
            "critical",
            "模板契约未确认",
            "template/format-contract.json",
            "format-contract status 不是 confirmed。",
            "完成模板契约确认后再排版（thesis-template-layout）。",
        )

    # C-05 profile/evidence refs
    if thesis.get("project", {}).get("status") != "confirmed":
        add_issue(
            issues,
            "C-05",
            "critical",
            "项目画像未确认",
            "thesis.json:project.status",
            "ch3-ch6 需要 confirmed 的 project.status。",
            "先确认 project/profile.json（thesis-project-comprehension）。",
        )
    for p, txt in drafts.items():
        if p.startswith("drafts/03") or p.startswith("drafts/04") or p.startswith("drafts/05") or p.startswith("drafts/06"):
            for m in re.findall(r"path:\s*([^\n]+)", txt):
                path = m.strip().strip('"').strip("'")
                root_key = path.split(".")[0].split("[")[0]
                if root_key not in profile:
                    add_issue(
                        issues,
                        "C-05",
                        "critical",
                        "evidence_refs 路径无法解析",
                        p,
                        f"evidence path `{path}` 在 project/profile.json 中不存在。",
                        "修正 evidence_refs 或更新 project/profile.json。",
                    )

    # C-01 C-02 C-03 C-08
    for p, txt in drafts.items():
        cites = find_citations(txt)
        used_cites.extend(cites)
        for k in cites:
            if k not in lib_map:
                add_issue(
                    issues,
                    "C-01",
                    "critical",
                    "未解析引用键",
                    p,
                    f"引用键 `[@{k}]` 不在 library/metadata.json。",
                    "补充该文献或修正文献键（literature-acquisition / academic-drafting）。",
                )
        for aid in re.findall(r"\{\{(?:fig|tab|eq):([^}]+)\}\}", txt):
            used_assets.append(aid)
            if aid not in asset_ids:
                add_issue(
                    issues,
                    "C-02",
                    "critical",
                    "未解析资产引用",
                    p,
                    f"资源 `{{{{fig/tab/eq:{aid}}}}}` 不在 assets/manifest.json。",
                    "生成对应资产并登记 manifest（thesis-assets）。",
                )
        for sid in re.findall(r"\[\[sec:([^\]]+)\]\]", txt):
            if sid not in section_ids:
                add_issue(
                    issues,
                    "C-03",
                    "critical",
                    "未解析章节引用",
                    p,
                    f"章节引用 `[[sec:{sid}]]` 不在 outline 中。",
                    "修正 sec 引用或补充 outline 章节。",
                )
        for todo in find_todos(txt):
            add_issue(
                issues,
                "C-08",
                "critical",
                "仍存在 TODO 标记",
                p,
                f"检测到 {todo}。",
                "补齐内容并删除 TODO（academic-drafting）。",
            )

    if used_assets and not user_inputs.get("diagram_dir_confirmed"):
        add_issue(
            issues,
            "M-17",
            "medium",
            "图表产物目录尚未由用户确认",
            "thesis.json:user_inputs.diagram_dir_confirmed",
            "草稿里已经出现图表引用，但还没有记录用户确认过图表保存路径或编辑回传路径。",
            "先向用户说明 Mermaid 或 draw.io 产物放在什么位置，等用户确认可用后再继续排版。",
        )

    for aid in sorted(set(used_assets)):
        asset = next((item for item in assets if item.get("id") == aid), None)
        if not asset or asset.get("type") != "figure":
            continue
        if not figure_asset_ready_for_docx(asset):
            add_issue(
                issues,
                "H-18",
                "high",
                "图表资产尚未导出为 docx 可插入图片",
                f"assets/manifest.json:{aid}",
                f"图表 `{aid}` 已登记，但当前 file/render_file 还不是可直接插入 docx 的图片，或 ready_for_docx=false。",
                "请先导出 PNG/JPG 到 assets/figures 后重新登记图表资产，再进入 layout_generate_docx.py。",
            )

    # C-04 mandatory fields for cited entries
    cited_unique = sorted(set(used_cites))
    for k in cited_unique:
        e = lib_map.get(k)
        if not e:
            continue
        missing = []
        if not e.get("title"):
            missing.append("title")
        if not e.get("authors"):
            missing.append("authors")
        if not e.get("year"):
            missing.append("year")
        if not e.get("type"):
            missing.append("type")
        if missing:
            add_issue(
                issues,
                "C-04",
                "critical",
                "被引用文献关键字段缺失",
                f"library/metadata.json:{k}",
                f"被引用条目 `{k}` 缺少字段: {', '.join(missing)}。",
                "补全文献元数据后再引用（literature-acquisition）。",
            )

        if e.get("language") == "en" and e.get("type") == "journal":
            detail_missing = missing_journal_detail_fields(e)
            if detail_missing:
                add_issue(
                    issues,
                    "H-19",
                    "high",
                    "英文期刊文献缺少卷期页信息",
                    f"library/metadata.json:{k}",
                    (
                        f"`{k}` 为英文期刊文献，但缺少 {', '.join(detail_missing)}。"
                        " 参考文献应补齐为 volume(issue): pages。"
                    ),
                    "重新运行 literature_search.py 补全元数据，或由用户手工补齐 volume、issue、pages。",
                )

        if e.get("language") == "en" and e.get("type") == "conference":
            detail_missing = missing_conference_detail_fields(e)
            if detail_missing:
                add_issue(
                    issues,
                    "H-20",
                    "high",
                    "英文论文集文献缺少论文集字段",
                    f"library/metadata.json:{k}",
                    (
                        f"`{k}` 为英文会议/论文集文献，但缺少 {', '.join(detail_missing)}。"
                        " 应尽量补齐 In: editors. booktitle. pub_place: publisher, year: pages。"
                    ),
                    "优先重新运行 literature_search.py 让 CrossRef 补全 booktitle、publisher、pub_place、pages、isbn、editors，仍缺失时再手工补录。",
                )

        if e.get("language") == "en" and not e.get("abstract_available") and not e.get("full_text_path"):
            add_issue(
                issues,
                "H-22",
                "high",
                "??????????????????",
                f"library/metadata.json:{k}",
                (
                    f"`{k}` ?????????????????"
                    " ??????????????????DOI ???????????????????????"
                ),
                "?????????????? PDF/?????????????",
            )


        if e.get("language") == "zh" and e.get("type") == "journal":
            detail_missing = missing_journal_detail_fields(e)
            if detail_missing:
                add_issue(
                    issues,
                    "M-18",
                    "medium",
                    "中文期刊文献建议手工补齐卷期页",
                    f"library/metadata.json:{k}",
                    (
                        f"`{k}` 为中文期刊文献，当前缺少 {', '.join(detail_missing)}。"
                        " 中文文献请由用户自行核对并补齐卷号(期号): 起页-止页。"
                    ),
                    "提醒用户按原始中文文献或知网/万方页面手工补齐。",
                )

        if e.get("language") == "zh" and e.get("type") == "conference":
            detail_missing = missing_conference_detail_fields(e)
            if detail_missing:
                add_issue(
                    issues,
                    "M-19",
                    "medium",
                    "中文论文集文献建议手工补齐论文集字段",
                    f"library/metadata.json:{k}",
                    (
                        f"`{k}` 为中文论文集文献，当前缺少 {', '.join(detail_missing)}。"
                        " 中文论文集请由用户自行补齐主编、论文集名、出版地、出版社、起止页等信息。"
                    ),
                    "提醒用户根据原始论文集封面页和目录页手工补录。",
                )

    # C-09 fabricated numbers heuristic
    test_text = drafts.get("drafts/06-system-test.md", "")
    if re.search(r"(平均响应时间|QPS|TPS|并发数)\s*[:：]\s*\d", test_text):
        add_issue(
            issues,
            "C-09",
            "critical",
            "测试章节出现疑似量化结论",
            "drafts/06-system-test.md",
            "检测到测试量化数字，请核实是否有真实测量依据。",
            "如无实测依据，改为定性表述。",
        )

    # C-10 unverifiable citations used heavily
    cite_counter = Counter(used_cites)
    for k, count in cite_counter.items():
        e = lib_map.get(k)
        if e and e.get("verification_status") == "unverifiable" and count >= 3:
            add_issue(
                issues,
                "C-10",
                "critical",
                "无法验证的文献被大量引用",
                f"library/metadata.json:{k}",
                f"`{k}` 标记为 unverifiable，但被引用了 {count} 次。该文献可能不存在或为编造。",
                "用 literature_verify.py 重新验证，或替换为已验证文献。",
            )

    # C-11 DOI format anomaly check
    for k in cited_unique:
        e = lib_map.get(k)
        if not e:
            continue
        doi = e.get("doi")
        if doi and not re.match(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$", str(doi)):
            add_issue(
                issues,
                "C-11",
                "critical",
                "DOI 格式异常",
                f"library/metadata.json:{k}",
                f"`{k}` 的 DOI `{doi}` 不符合标准格式 (10.XXXX/YYYY)。",
                "修正 DOI 字符串或删除虚假 DOI。",
            )

    # C-12 heavy citation of unreadable paper
    for k, count in cite_counter.items():
        e = lib_map.get(k)
        if not e:
            continue
        if count >= 5 and e.get("extraction_quality") in ("failed", None) and not e.get("abstract"):
            add_issue(
                issues,
                "C-12",
                "critical",
                "高频引用不可读文献",
                f"library/metadata.json:{k}",
                f"`{k}` 被引用 {count} 次但无全文也无摘要。疑似模型编造引用。",
                "确认该文献确实存在并提取正文，或减少引用。",
            )

    # H-01 word budget
    tol = 0.15
    for ch in thesis.get("outline", []):
        budget = ch.get("word_budget") or 0
        actual = ch.get("word_actual") or 0
        if budget > 0:
            low = budget * (1 - tol)
            high = budget * (1 + tol)
            if actual < low or actual > high:
                add_issue(
                    issues,
                    "H-01",
                    "high",
                    "章节字数偏离预算",
                    f"thesis.json:outline:{ch.get('id')}",
                    f"word_actual={actual}, word_budget={budget}，超出±15%范围。",
                    "按章节预算补写或精简（academic-drafting Revise）。",
                )

    # M-09 citation density
    intro = drafts.get("drafts/01-introduction.md", "")
    intro_section = re.search(r"## 1\.2[\s\S]*?(?=\n## |\Z)", intro)
    if intro_section:
        c = len(find_citations(intro_section.group(0)))
        if c < policy["intro_cites_min"]:
            add_issue(
                issues,
                "M-09",
                "medium",
                "绪论研究现状引用不足",
                "drafts/01-introduction.md:1.2",
                f"当前引用数 {c}，低于 {policy['degree']} 默认阈值 {policy['intro_cites_min']}。",
                "补充相关研究引用（literature-acquisition + academic-drafting）。",
            )
    rw = drafts.get("drafts/02-related-work.md", "")
    for m in re.finditer(r"(## 2\.\d[\s\S]*?)(?=\n## |\Z)", rw):
        sec = m.group(1)
        c = len(find_citations(sec))
        if c < policy["related_cites_min"]:
            title = sec.splitlines()[0].strip()
            add_issue(
                issues,
                "M-09",
                "medium",
                "相关技术小节引用不足",
                f"drafts/02-related-work.md:{title}",
                f"{title} 当前引用数 {c}，低于 {policy['degree']} 默认阈值 {policy['related_cites_min']}。",
                "为该小节补充适量相关引用，避免只写概念定义。",
            )

    # M-10 M-11 literature baseline
    total = len(library)
    en = sum(1 for e in library if e.get("language") == "en")
    ratio = en / total if total else 0
    if ratio < policy["english_ratio_min"]:
        add_issue(
            issues,
            "M-10",
            "medium",
            "英文文献比例不足",
            "library/metadata.json",
            f"英文比例 {ratio:.1%}，低于 {policy['degree']} 默认阈值 {policy['english_ratio_min']:.0%}。",
            "补充英文文献（literature-acquisition）。",
        )
    if total < policy["total_refs_min"]:
        add_issue(
            issues,
            "M-11",
            "medium",
            "文献总量不足",
            "library/metadata.json",
            f"当前 {total} 条，低于 {policy['degree']} 默认阈值 {policy['total_refs_min']}。",
            "继续扩充文献库，但不要为了凑数牺牲相关性。",
        )

    # H-05 simple blacklist
    blacklist = ["随着", "在当今社会", "众所周知", "信息化时代的到来"]
    for p, txt in drafts.items():
        for b in blacklist:
            if b in txt:
                add_issue(
                    issues,
                    "H-05",
                    "high",
                    "检测到模板化套话",
                    p,
                    f"出现短语 `{b}`。",
                    "改为具体事实描述（academic-drafting Revise）。",
                )
                break

    # H-06 stale assets
    for a in assets:
        if a.get("stale") is True:
            add_issue(
                issues,
                "H-06",
                "high",
                "存在过期资产",
                "assets/manifest.json",
                f"资产 `{a.get('id')}` 标记 stale=true。",
                "重生成并更新引用（thesis-assets）。",
            )

    # H-07 finalized
    not_finalized = [c.get("id") for c in thesis.get("outline", []) if c.get("status") != "finalized"]
    if not_finalized:
        add_issue(
            issues,
            "H-07",
            "high",
            "章节尚未 finalized",
            "thesis.json:outline",
            f"未 finalized 章节: {', '.join(not_finalized)}。",
            "完成修订后将章节状态升为 finalized（academic-drafting + orchestrator）。",
        )

    # H-08 duplicate entries with near-identical titles
    titles = [(e.get("id"), (e.get("title") or "").lower()) for e in library if e.get("id")]
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            t1, t2 = titles[i][1], titles[j][1]
            if len(t1) > 20 and len(t2) > 20:
                # Simple similarity: common prefix length ratio
                min_len = min(len(t1), len(t2))
                common = 0
                for c1, c2 in zip(t1, t2):
                    if c1 == c2:
                        common += 1
                    else:
                        break
                if common / min_len > 0.85:
                    add_issue(
                        issues,
                        "H-08",
                        "high",
                        "疑似重复文献条目",
                        f"library/metadata.json:{titles[i][0]},{titles[j][0]}",
                        f"`{titles[i][0]}` 和 `{titles[j][0]}` 标题相似度 > 85%，可能为同一篇论文重复入库。",
                        "检查并合并重复条目。",
                    )
                    break  # Only flag each pair once

    # Medium checks
    cite_count = Counter(used_cites)
    unused_lib = [e.get("id") for e in library if e.get("id") and e.get("id") not in cite_count]
    if unused_lib:
        add_issue(
            issues,
            "M-01",
            "medium",
            "存在未使用文献",
            "library/metadata.json",
            f"未被引用文献 {len(unused_lib)} 条。",
            "在相关章节补充引用，或保留为储备文献。",
        )
    if assets:
        unused_assets = [a.get("id") for a in assets if a.get("id") and a.get("id") not in set(used_assets)]
        if unused_assets:
            add_issue(
                issues,
                "M-02",
                "medium",
                "存在未使用资产",
                "assets/manifest.json",
                f"未被引用资产 {len(unused_assets)} 个。",
                "补充正文引用或删除冗余资产。",
            )

    # M-03 orphan sections (TODO or too short)
    for p, txt in drafts.items():
        for sec in re.finditer(r"^##\s+([^\n]+)\n([\s\S]*?)(?=^##\s+|\Z)", txt, flags=re.M):
            title = sec.group(1)
            body = sec.group(2)
            if "[TODO:" in body:
                add_issue(
                    issues,
                    "M-03",
                    "medium",
                    "小节内容未完成",
                    f"{p}:{title}",
                    "检测到 TODO 占位或未完成段落。",
                    "补齐正文内容并删除占位。",
                )

    # M-04 paragraph length
    for p, txt in drafts.items():
        for para in re.split(r"\n\s*\n", txt):
            para = para.strip()
            if not para or para.startswith("---") or para.startswith("#") or para.startswith("[TODO:"):
                continue
            l = len(re.findall(r"[\u4e00-\u9fff]", para))
            if l and (l < 80 or l > 500):
                add_issue(
                    issues,
                    "M-04",
                    "medium",
                    "段落长度异常",
                    p,
                    f"检测到段落中文字符约 {l}，超出 80-500 范围。",
                    "拆分过长段落或补充过短段落信息。",
                )
                break

    # M-05 repeated same cite in paragraph
    for p, txt in drafts.items():
        for para in re.split(r"\n\s*\n", txt):
            cites = find_citations(para)
            if cites and any(v > 1 for v in Counter(cites).values()):
                add_issue(
                    issues,
                    "M-05",
                    "medium",
                    "同段重复引用同一文献",
                    p,
                    "同一段内重复出现相同 cite-key。",
                    "保留一次引用即可，避免冗余。",
                )
                break

    # H-09 undergrad defense: implementation evidence refs
    impl_evidence = []
    for p in ["drafts/04-system-design.md", "drafts/05-implementation.md", "drafts/06-system-test.md"]:
        txt = drafts.get(p, "")
        impl_evidence.extend(find_evidence_refs(txt))
    if drafts.get("drafts/05-implementation.md", "") and \
       len(sorted(set(impl_evidence))) < policy["implementation_evidence_min"]:
        add_issue(
            issues,
            "H-09",
            "high",
            "实现过程缺少可追溯工作量证据",
            "drafts/04-system-design.md,drafts/05-implementation.md,drafts/06-system-test.md",
            f"当前仅检测到 {len(sorted(set(impl_evidence)))} 处 `path:` 证据引用，低于 {policy['degree']} 默认阈值 {policy['implementation_evidence_min']}，难以支撑答辩时对具体工作量的说明。",
            "在实现/设计/测试章节补充代码、配置、接口或数据结构的 evidence path。",
        )

    # H-10 undergrad defense: framework selection rationale
    design_impl_text = "\n".join([
        drafts.get("drafts/03-requirements.md", ""),
        drafts.get("drafts/04-system-design.md", ""),
        drafts.get("drafts/05-implementation.md", ""),
    ])
    if design_impl_text and not has_selection_rationale(design_impl_text):
        add_issue(
            issues,
            "H-10",
            "high",
            "缺少技术选型理由说明",
            "drafts/04-system-design.md,drafts/05-implementation.md",
            "没有明显检测到“选用什么技术，以及为什么这样选”的成段说明。",
            "补充框架、数据库、认证方案等技术选型理由，强调与项目需求的匹配关系。",
        )

    # H-11 undergrad defense: challenge/solution narrative
    challenge_text = "\n".join([
        drafts.get("drafts/05-implementation.md", ""),
        drafts.get("drafts/06-system-test.md", ""),
    ])
    if challenge_text and not has_challenge_solution_narrative(challenge_text):
        add_issue(
            issues,
            "H-11",
            "high",
            "缺少开发难点与解决过程",
            "drafts/05-implementation.md,drafts/06-system-test.md",
            "没有明显检测到开发过程中遇到的问题、定位过程和解决办法，这会削弱本科毕设答辩中的工作量体现。",
            "补充至少 1-2 个真实开发难点，并写清楚原因、排查过程和最终解决方案。",
        )

    # M-12 screenshot realism
    screenshot_assets = [
        a for a in assets
        if a.get("type") == "figure"
        and str(a.get("source_format", "")).lower() == "manual-screenshot"
    ]
    screenshot_refs = [
        aid for aid in set(used_assets)
        if any(
            a.get("id") == aid and str(a.get("source_format", "")).lower() == "manual-screenshot"
            for a in assets
        )
    ]
    if drafts.get("drafts/05-implementation.md", "") and not screenshot_refs:
        add_issue(
            issues,
            "M-12",
            "medium",
            "实现章节缺少截图型证据",
            "drafts/05-implementation.md,assets/manifest.json",
            f"当前检测到 {len(screenshot_assets)} 个手工截图资产，但正文没有引用，或尚未上传截图。",
            "补充页面截图、核心代码截图或运行结果截图，登记到 manifest 后在实现章节用 {{fig:...}} 引用。",
        )

    debug_screenshot_assets = [a for a in screenshot_assets if screenshot_usage_phase(a) == "debugging"]
    debug_screenshot_refs = [
        aid for aid in screenshot_refs
        if any(a.get("id") == aid and screenshot_usage_phase(a) == "debugging" for a in screenshot_assets)
    ]
    if drafts.get("drafts/06-system-test.md", "") and not debug_screenshot_refs:
        add_issue(
            issues,
            "H-21",
            "high",
            "??????????????",
            "drafts/06-system-test.md,assets/manifest.json",
            (
                f"????? {len(debug_screenshot_assets)} ?????????????"
                "????????????????????????????????"
            ),
            "????????????????????????? {{fig:...}} ?????",
        )


    weak_screenshot_assets = [
        a for a in screenshot_assets
        if not str(a.get("proof_note") or "").strip()
        or is_generic_screenshot_caption(a.get("caption"))
    ]
    if weak_screenshot_assets:
        weak_ids = ", ".join(a.get("id") for a in weak_screenshot_assets[:5] if a.get("id"))
        add_issue(
            issues,
            "M-15",
            "medium",
            "截图证明点说明偏弱",
            "assets/manifest.json",
            f"手工截图 {weak_ids or 'N/A'} 缺少 proof_note，或 caption 过于泛化，后续很难在正文里自然解释它证明了什么。",
            "在 assets/screenshots/metadata.json 中补充 caption、proof、module、section_ref 后重新运行 register_manual_figures.py。",
        )

    # M-13 style too AI-sounding
    ai_hits_total = 0
    ai_hits_list = []
    for p, txt in drafts.items():
        c, hits = count_ai_sounding_phrases(txt)
        ai_hits_total += c
        ai_hits_list.extend(hits)
    if ai_hits_total >= 3:
        uniq_hits = ", ".join(sorted(set(ai_hits_list))[:5])
        add_issue(
            issues,
            "M-13",
            "medium",
            "写作口吻偏空泛或 AI 腔",
            "drafts/*",
            f"检测到 {ai_hits_total} 处偏空泛表达，例如：{uniq_hits}。",
            "改成更贴近本科生项目复盘的表达，多写自己做了什么、怎么做、遇到什么问题，少写宏大空话。",
        )

    # M-14 screenshot references should appear naturally in prose
    screenshot_asset_ids = {
        a.get("id") for a in assets
        if a.get("type") == "figure"
        and str(a.get("source_format", "")).lower() == "manual-screenshot"
    }
    bad_screenshot_paras = []
    for p, txt in drafts.items():
        for para in re.split(r"\n\s*\n", txt):
            para = para.strip()
            if not para:
                continue
            para_figs = re.findall(r"\{\{fig:([^}]+)\}\}", para)
            if not para_figs:
                continue
            if not any(fig_id in screenshot_asset_ids for fig_id in para_figs):
                continue
            if not has_natural_screenshot_context(para):
                bad_screenshot_paras.append(p)
                break
    if bad_screenshot_paras:
        add_issue(
            issues,
            "M-14",
            "medium",
            "截图引用不够自然",
            ",".join(sorted(set(bad_screenshot_paras))),
            "检测到截图引用可能是单独摆放或缺少上下文解释，不利于论文叙述自然展开。",
            "先写清模块、页面、问题或结果，再在句中自然引用截图，例如“如 {{fig:shot-01}} 所示，订单管理页面已经支持分页筛选”。",
        )

    # Low: terminology consistency
    all_text = "\n".join(drafts.values())
    if "SpringBoot" in all_text and "Spring Boot" in all_text:
        add_issue(
            issues,
            "L-01",
            "low",
            "术语写法不一致",
            "drafts/*",
            "同时出现 SpringBoot 与 Spring Boot。",
            "统一术语写法，建议使用 Spring Boot。",
        )

    counts = Counter(i["level"] for i in issues)
    for lv in ["critical", "high", "medium", "low"]:
        counts.setdefault(lv, 0)
    if counts["critical"] > 0:
        verdict = "fail-critical"
    elif counts["high"] > 0:
        verdict = "fail-high"
    elif counts["medium"] > 0:
        verdict = "warn"
    else:
        verdict = "pass"

    # Build report
    lines = []
    lines.append("# Thesis Preflight Report")
    lines.append("")
    lines.append(f"**Generated**: {now}")
    lines.append(f"**Workspace**: {ROOT}")
    lines.append(f"**Thesis**: {thesis.get('meta', {}).get('title', '')}")
    lines.append(
        f"**Verdict**: {'✅' if verdict == 'pass' else '❌'} {verdict} "
        f"({counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low)"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    for lv, title in [("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low")]:
        lv_issues = [i for i in issues if i["level"] == lv]
        lines.append(f"## {title} ({len(lv_issues)})")
        lines.append("")
        for i in lv_issues:
            lines.append(f"### {i['check_id']} · {i['title']}")
            lines.append("")
            lines.append(f"**Location**: `{i['location']}`")
            lines.append(f"**Detail**: {i['detail']}")
            lines.append(f"**Fix**: {i['fix_hint']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    route = defaultdict(int)
    for i in issues:
        if "literature-acquisition" in i["fix_hint"]:
            route["literature-acquisition"] += 1
        if "academic-drafting" in i["fix_hint"]:
            route["academic-drafting"] += 1
        if "thesis-assets" in i["fix_hint"]:
            route["thesis-assets"] += 1
        if "thesis-project-comprehension" in i["fix_hint"]:
            route["thesis-project-comprehension"] += 1
        if "thesis-template-layout" in i["fix_hint"]:
            route["thesis-template-layout"] += 1
    lines.append("## Fix routing summary")
    lines.append("")
    lines.append("| Count | Skill to invoke |")
    lines.append("|---:|---|")
    for k, v in sorted(route.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {v} | `{k}` |")
    if not route:
        lines.append("| 0 | `none` |")
    lines.append("")

    out_path = os.path.join(ROOT, "output", "preflight-report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(
        json.dumps(
            {
                "verdict": verdict,
                "counts": {
                    "critical": counts["critical"],
                    "high": counts["high"],
                    "medium": counts["medium"],
                    "low": counts["low"],
                },
                "report_path": "output/preflight-report.md",
                "generated_at": now,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
