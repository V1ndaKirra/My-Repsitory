# -*- coding: utf-8 -*-
"""Render thesis markdown drafts + assets into a format-compliant .docx.

Implements:
- Cover page (独立分节, 不显示页码)
- Front matter section (中摘要/英摘要/目录, 罗马页码 I/II/III)
- Body section (正文 + 参考文献, 阿拉伯页码从 1 重新计数,
  页眉 "<学校名称> · <题目>", 页脚 "第 X 页 共 Y 页")
- 字体: 正文宋体 12pt, H1 黑体 16pt, H2 黑体 14pt, H3 宋体加粗 12pt
- 段落: 1.5 倍行距, 首行缩进 2 字符
- TOC: 使用 Word TOC 域 (F9 更新)
- 图表: {{fig:id}} / {{tab:id}} 按章节编号为 "图 X-Y" / "表 X-Y",
  首次引用后插入图片或三线表 + 题注
- 引用: [@cite-key] 按首次出现顺序编号为 [N], GB/T 7714 参考文献列表
"""
import json
import os
import re
from datetime import datetime, timezone

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Emu, Inches
from thesis_schema import load_thesis_json

ROOT = os.environ.get("THESIS_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# -------------------- XML helpers --------------------

def _qn(tag): return qn(tag)


def set_run_cjk_font(run, zh="宋体", en="Times New Roman", size_pt=None, bold=False):
    """Set run font for CJK and Latin, with optional size and bold."""
    rpr = run._element.get_or_add_rPr()
    rFonts = rpr.find(_qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rpr.append(rFonts)
    rFonts.set(_qn("w:ascii"), en)
    rFonts.set(_qn("w:hAnsi"), en)
    rFonts.set(_qn("w:cs"), en)
    rFonts.set(_qn("w:eastAsia"), zh)
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if bold:
        run.bold = True


def set_par_line_spacing(par, line_spacing=1.5):
    pPr = par._element.get_or_add_pPr()
    spacing = pPr.find(_qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        pPr.append(spacing)
    spacing.set(_qn("w:line"), str(int(240 * line_spacing)))
    spacing.set(_qn("w:lineRule"), "auto")
    spacing.set(_qn("w:before"), "0")
    spacing.set(_qn("w:after"), "0")


def set_first_line_indent_chars(par, chars=2):
    pPr = par._element.get_or_add_pPr()
    ind = pPr.find(_qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(_qn("w:firstLineChars"), str(int(chars * 100)))


def add_page_break_before(par):
    pPr = par._element.get_or_add_pPr()
    pb = OxmlElement("w:pageBreakBefore")
    pPr.append(pb)


def insert_page_field(paragraph, kind="PAGE"):
    """Insert a simple Word field like PAGE / NUMPAGES into a paragraph."""
    run = paragraph.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(_qn("w:instr"), f" {kind}   \\* MERGEFORMAT ")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    run._element.append(fld)


def configure_section_pg_num(section, fmt="decimal", start=None):
    """Configure page number format and start for a section."""
    sectPr = section._sectPr
    pgNum = sectPr.find(_qn("w:pgNumType"))
    if pgNum is None:
        pgNum = OxmlElement("w:pgNumType")
        sectPr.append(pgNum)
    pgNum.set(_qn("w:fmt"), fmt)
    if start is not None:
        pgNum.set(_qn("w:start"), str(start))
    else:
        if pgNum.get(_qn("w:start")) is not None:
            del pgNum.attrib[_qn("w:start")]


def set_title_pg(section):
    sectPr = section._sectPr
    titlePg = sectPr.find(_qn("w:titlePg"))
    if titlePg is None:
        titlePg = OxmlElement("w:titlePg")
        sectPr.append(titlePg)


def unset_title_pg(section):
    sectPr = section._sectPr
    titlePg = sectPr.find(_qn("w:titlePg"))
    if titlePg is not None:
        sectPr.remove(titlePg)


def add_toc_field(paragraph, levels=3):
    """Insert a Word TOC field as separate runs (Word-compliant structure).

    Document settings also enable auto field update on open so the TOC
    fills in automatically when the user opens the file.
    """
    def mk_run():
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(_qn("w:ascii"), FONT_BODY_EN)
        rFonts.set(_qn("w:hAnsi"), FONT_BODY_EN)
        rFonts.set(_qn("w:eastAsia"), FONT_BODY_ZH)
        rpr.append(rFonts)
        sz = OxmlElement("w:sz"); sz.set(_qn("w:val"), "24")
        rpr.append(sz)
        r.append(rpr)
        return r

    p_el = paragraph._p

    r1 = mk_run()
    fld1 = OxmlElement("w:fldChar"); fld1.set(_qn("w:fldCharType"), "begin")
    fld1.set(_qn("w:dirty"), "true")
    r1.append(fld1)
    p_el.append(r1)

    r2 = mk_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f' TOC \\o "1-{levels}" \\h \\z \\u '
    r2.append(instr)
    p_el.append(r2)

    r3 = mk_run()
    fld2 = OxmlElement("w:fldChar"); fld2.set(_qn("w:fldCharType"), "separate")
    r3.append(fld2)
    p_el.append(r3)

    r4 = mk_run()
    t = OxmlElement("w:t")
    t.text = "（目录将在打开文档时自动生成；如未显示，请全选后按 F9 更新）"
    r4.append(t)
    p_el.append(r4)

    r5 = mk_run()
    fld3 = OxmlElement("w:fldChar"); fld3.set(_qn("w:fldCharType"), "end")
    r5.append(fld3)
    p_el.append(r5)


def enable_update_fields_on_open(doc):
    """Set <w:updateFields w:val='true'/> in settings.xml so Word refreshes TOC on open."""
    settings = doc.settings.element
    existing = settings.find(_qn("w:updateFields"))
    if existing is None:
        upd = OxmlElement("w:updateFields")
        upd.set(_qn("w:val"), "true")
        settings.append(upd)
    else:
        existing.set(_qn("w:val"), "true")


def set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    """Set individual borders on a table cell. None = remove."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(_qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for side, sz in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = tcBorders.find(_qn(f"w:{side}"))
        if el is not None:
            tcBorders.remove(el)
        b = OxmlElement(f"w:{side}")
        if sz is None:
            b.set(_qn("w:val"), "nil")
        else:
            b.set(_qn("w:val"), "single")
            b.set(_qn("w:sz"), str(sz))
            b.set(_qn("w:color"), "000000")
        tcBorders.append(b)


def set_header_paragraph_border(paragraph):
    """Add a bottom border under a header paragraph (常见于论文页眉)."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = pPr.find(_qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(_qn("w:val"), "single")
    bottom.set(_qn("w:sz"), "6")
    bottom.set(_qn("w:space"), "1")
    bottom.set(_qn("w:color"), "000000")
    pBdr.append(bottom)


# -------------------- Style helpers --------------------

FONT_BODY_ZH = "宋体"
FONT_BODY_EN = "Times New Roman"
FONT_HEAD_ZH = "黑体"
SUPPORTED_FIGURE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


def style_body_paragraph(par):
    set_par_line_spacing(par, 1.5)
    set_first_line_indent_chars(par, 2)
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def add_body_paragraph(doc, text, runs_spec=None):
    par = doc.add_paragraph()
    style_body_paragraph(par)
    if runs_spec is None:
        runs_spec = [(text, False)]
    for chunk, is_bold in runs_spec:
        if not chunk:
            continue
        run = par.add_run(chunk)
        set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 12, bold=is_bold)
    return par


def _force_zero_indent(par):
    """Force a paragraph to left-align from margin (无首行缩进/无左缩进).

    Needed for 二级/三级标题的"左起顶格"要求, 防止继承 Heading 样式默认缩进.
    """
    pPr = par._element.get_or_add_pPr()
    ind = pPr.find(_qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(_qn("w:left"), "0")
    ind.set(_qn("w:leftChars"), "0")
    ind.set(_qn("w:firstLine"), "0")
    ind.set(_qn("w:firstLineChars"), "0")


def add_heading_1(doc, text, page_break=True):
    """一级标题: 三号黑体 (16pt), 居中, 1.5 倍行距, 段前段后各 1 行."""
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_par_line_spacing(par, 1.5)
    pPr = par._element.get_or_add_pPr()
    spacing = pPr.find(_qn("w:spacing"))
    spacing.set(_qn("w:before"), "0")
    spacing.set(_qn("w:after"), "0")
    spacing.set(_qn("w:beforeLines"), "100")
    spacing.set(_qn("w:afterLines"), "100")
    if page_break:
        add_page_break_before(par)
    pStyle = OxmlElement("w:pStyle"); pStyle.set(_qn("w:val"), "Heading1")
    pPr.insert(0, pStyle)
    run = par.add_run(text)
    set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 16, bold=True)
    run.font.color.rgb = RGBColor(0, 0, 0)
    return par


def add_heading_2(doc, text):
    """二级标题: 四号黑体 (14pt), 左起顶格, 1.5 倍行距."""
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_par_line_spacing(par, 1.5)
    _force_zero_indent(par)
    pPr = par._element.get_or_add_pPr()
    pStyle = OxmlElement("w:pStyle"); pStyle.set(_qn("w:val"), "Heading2")
    pPr.insert(0, pStyle)
    run = par.add_run(text)
    set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 14, bold=True)
    return par


def add_heading_3(doc, text):
    """三级标题: 小四号宋体加粗 (12pt), 左起顶格, 1.5 倍行距."""
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_par_line_spacing(par, 1.5)
    _force_zero_indent(par)
    pPr = par._element.get_or_add_pPr()
    pStyle = OxmlElement("w:pStyle"); pStyle.set(_qn("w:val"), "Heading3")
    pPr.insert(0, pStyle)
    run = par.add_run(text)
    set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 12, bold=True)
    return par


def add_caption(doc, text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_par_line_spacing(par, 1.5)
    run = par.add_run(text)
    set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5, bold=False)
    return par


def add_centered_image(doc, image_path, width_cm=13.0):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_par_line_spacing(par, 1.5)
    run = par.add_run()
    run.add_picture(image_path, width=Cm(width_cm))
    return par


def add_centered_asset_placeholder(doc, text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_par_line_spacing(par, 1.5)
    run = par.add_run(text)
    set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5, bold=False)
    return par


def resolve_figure_render_path(asset):
    candidate = asset.get("render_file") or asset.get("file")
    if not candidate:
        return None
    ext = os.path.splitext(candidate)[1].lower()
    if ext not in SUPPORTED_FIGURE_EXTS:
        return None
    if asset.get("ready_for_docx") is False:
        return None
    abs_path = os.path.join(ROOT, candidate)
    if not os.path.exists(abs_path):
        return None
    return abs_path


def _mark_header_row(row):
    """Mark a row as a table header so it repeats on page breaks."""
    trPr = row._tr.get_or_add_trPr()
    tblHeader = OxmlElement("w:tblHeader")
    tblHeader.set(_qn("w:val"), "true")
    trPr.append(tblHeader)


def _center_table(table):
    """Center the table horizontally on the page."""
    tbl = table._tbl
    tblPr = tbl.find(_qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    jc = tblPr.find(_qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        tblPr.append(jc)
    jc.set(_qn("w:val"), "center")
    tblInd = tblPr.find(_qn("w:tblInd"))
    if tblInd is None:
        tblInd = OxmlElement("w:tblInd")
        tblPr.append(tblInd)
    tblInd.set(_qn("w:w"), "0")
    tblInd.set(_qn("w:type"), "dxa")


def add_three_line_table(doc, headers, rows):
    n_cols = len(headers)
    table = doc.add_table(rows=1 + len(rows), cols=n_cols)
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    table.autofit = True
    _center_table(table)

    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        cell = hdr_cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 10.5, bold=True)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    _mark_header_row(table.rows[0])

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(str(val))
            set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5, bold=False)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    last_row = len(rows)
    for row_idx, row in enumerate(table.rows):
        is_top = (row_idx == 0)
        is_header_bottom = (row_idx == 0)
        is_bottom = (row_idx == last_row)
        for cell in row.cells:
            top = 12 if is_top else None
            bottom_sz = 12 if is_bottom else (4 if is_header_bottom else None)
            set_cell_borders(cell, top=top, bottom=bottom_sz, left=None, right=None)
    return table


# -------------------- Markdown parsing --------------------

FRONT_MATTER_RE = re.compile(r"^---\s*$")
CITE_RE = re.compile(r"\[@([^\]]+)\]")
FIG_RE = re.compile(r"\{\{fig:([^}]+)\}\}")
TBL_RE = re.compile(r"\{\{tab:([^}]+)\}\}")


def strip_front_matter(md_text):
    lines = md_text.splitlines()
    if not lines or not FRONT_MATTER_RE.match(lines[0]):
        return md_text
    end = None
    for i in range(1, len(lines)):
        if FRONT_MATTER_RE.match(lines[i]):
            end = i
            break
    if end is None:
        return md_text
    return "\n".join(lines[end + 1:])


# -------------------- Citation index --------------------

def build_citation_index(drafts):
    """Assign GB/T 7714 numeric ids to cite-keys by first occurrence order."""
    order = []
    seen = set()
    for text in drafts:
        for m in CITE_RE.finditer(text):
            raw = m.group(1)
            for k in [x.strip().lstrip("@").strip() for x in raw.split(",")]:
                if k and k not in seen:
                    seen.add(k)
                    order.append(k)
    return {k: i + 1 for i, k in enumerate(order)}, order


def resolve_citations_inline(text, cite_index):
    def repl(m):
        raw = m.group(1)
        nums = []
        for k in [x.strip().lstrip("@").strip() for x in raw.split(",")]:
            if k in cite_index:
                nums.append(str(cite_index[k]))
        return "[" + ",".join(nums) + "]" if nums else m.group(0)
    return CITE_RE.sub(repl, text)


# -------------------- Asset numbering --------------------

def build_asset_numbers(drafts_seq):
    """
    Walk chapters in order; for each figure/table occurrence, assign 图 X-Y / 表 X-Y.
    X = chapter number, Y = per-chapter counter.
    Returns:
      fig_map: asset_id -> "X-Y"
      tbl_map: asset_id -> "X-Y"
      first_occ: asset_id -> chapter_index where first referenced
    """
    fig_map = {}
    tbl_map = {}
    first_occ_fig = {}
    first_occ_tbl = {}

    for ch_num, md in drafts_seq:
        fig_count = 0
        tbl_count = 0
        for m in FIG_RE.finditer(md):
            aid = m.group(1)
            if aid not in fig_map:
                fig_count += 1
                fig_map[aid] = f"{ch_num}-{fig_count}"
                first_occ_fig[aid] = ch_num
        for m in TBL_RE.finditer(md):
            aid = m.group(1)
            if aid not in tbl_map:
                tbl_count += 1
                tbl_map[aid] = f"{ch_num}-{tbl_count}"
                first_occ_tbl[aid] = ch_num
    return fig_map, tbl_map


# -------------------- Rendering --------------------

def load_asset_manifest():
    path = os.path.join(ROOT, "assets", "manifest.json")
    if not os.path.exists(path):
        return {}
    data = json.load(open(path, "r", encoding="utf-8"))
    return {a["id"]: a for a in data}


def load_table(asset):
    path = os.path.join(ROOT, asset["file"])
    return json.load(open(path, "r", encoding="utf-8"))


def render_paragraph_with_assets(doc, text, cite_index, fig_map, tbl_map,
                                 assets, rendered_figs, rendered_tbls):
    """Render a paragraph text that may contain {{fig:}} / {{tab:}} / [@cite] placeholders.

    For the first occurrence of a figure/table in the document, we:
      1. Replace the inline reference with '图 X-Y' / '表 X-Y'.
      2. After the paragraph, append the figure/table with caption.
    """
    to_insert_after = []

    def fig_sub(m):
        aid = m.group(1)
        num = fig_map.get(aid)
        if num is None:
            return m.group(0)
        if aid not in rendered_figs:
            rendered_figs.add(aid)
            to_insert_after.append(("figure", aid))
        return f"图 {num}"

    def tbl_sub(m):
        aid = m.group(1)
        num = tbl_map.get(aid)
        if num is None:
            return m.group(0)
        if aid not in rendered_tbls:
            rendered_tbls.add(aid)
            to_insert_after.append(("table", aid))
        return f"表 {num}"

    text = FIG_RE.sub(fig_sub, text)
    text = TBL_RE.sub(tbl_sub, text)
    text = resolve_citations_inline(text, cite_index)

    add_body_paragraph(doc, text)

    for kind, aid in to_insert_after:
        asset = assets.get(aid)
        if asset is None:
            continue
        if kind == "figure":
            img_path = resolve_figure_render_path(asset)
            if img_path:
                add_centered_image(doc, img_path, width_cm=13.5)
            else:
                add_centered_asset_placeholder(
                    doc,
                    f"【图资源待导出：{asset.get('caption', aid)}（{aid}）】",
                )
            num = fig_map[aid]
            add_caption(doc, f"图 {num}  {asset['caption']}")
        else:
            num = tbl_map[aid]
            add_caption(doc, f"表 {num}  {asset['caption']}")
            tdata = load_table(asset)
            add_three_line_table(doc, tdata["headers"], tdata["rows"])


def render_chapter(doc, md_text, cite_index, fig_map, tbl_map, assets,
                   rendered_figs, rendered_tbls, page_break_on_h1=True,
                   emit_h1=True):
    body = strip_front_matter(md_text)
    lines = body.splitlines()
    i = 0
    pending_par = []

    def flush():
        if not pending_par:
            return
        txt = " ".join(pending_par).strip()
        pending_par.clear()
        if txt:
            render_paragraph_with_assets(
                doc, txt, cite_index, fig_map, tbl_map, assets,
                rendered_figs, rendered_tbls,
            )

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
            i += 1
            continue
        if line.startswith("### "):
            flush()
            add_heading_3(doc, line[4:].strip())
            i += 1
            continue
        if line.startswith("## "):
            flush()
            add_heading_2(doc, line[3:].strip())
            i += 1
            continue
        if line.startswith("# "):
            flush()
            if emit_h1:
                add_heading_1(doc, line[2:].strip(), page_break=page_break_on_h1)
            i += 1
            continue
        pending_par.append(line.strip())
        i += 1
    flush()


# -------------------- Sections --------------------

def setup_page_margins(section, contract):
    m = contract["page"]["margins_cm"]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(m["top"])
    section.bottom_margin = Cm(m["bottom"])
    section.left_margin = Cm(m["left"])
    section.right_margin = Cm(m["right"])
    section.header_distance = Cm(contract["page"].get("header_distance_cm", 1.5))
    section.footer_distance = Cm(contract["page"].get("footer_distance_cm", 1.75))


def clear_header_footer(section):
    for hf in (section.header, section.footer):
        for p in list(hf.paragraphs):
            for r in list(p.runs):
                r.text = ""


def set_footer_page_number(section, roman=False, pattern=None):
    """Set footer with page number. If pattern given (e.g. '第 {PAGE} 页 共 {NUMPAGES} 页'), use it."""
    footer = section.footer
    footer.is_linked_to_previous = False
    if footer.paragraphs:
        p = footer.paragraphs[0]
    else:
        p = footer.add_paragraph()
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if pattern is None:
        run = p.add_run()
        set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5)
        insert_page_field(p, "PAGE")
    else:
        parts = re.split(r"(\{PAGE\}|\{NUMPAGES\})", pattern)
        for part in parts:
            if part == "{PAGE}":
                insert_page_field(p, "PAGE")
            elif part == "{NUMPAGES}":
                insert_page_field(p, "NUMPAGES")
            elif part:
                run = p.add_run(part)
                set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5)


def set_header_text(section, text, with_border=True):
    header = section.header
    header.is_linked_to_previous = False
    if header.paragraphs:
        p = header.paragraphs[0]
    else:
        p = header.add_paragraph()
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if text:
        run = p.add_run(text)
        set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5)
    if with_border:
        set_header_paragraph_border(p)


def clear_header(section):
    header = section.header
    header.is_linked_to_previous = False
    if header.paragraphs:
        p = header.paragraphs[0]
        for r in list(p.runs):
            r._element.getparent().remove(r._element)


def clear_footer(section):
    footer = section.footer
    footer.is_linked_to_previous = False
    if footer.paragraphs:
        p = footer.paragraphs[0]
        for r in list(p.runs):
            r._element.getparent().remove(r._element)


# -------------------- Cover --------------------

def render_cover(doc, meta):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta["school"])
    set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 22, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("本科毕业设计（论文）")
    set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 18, bold=True)

    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("题    目")
    set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 16, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta["title"])
    set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 20, bold=True)

    for _ in range(3):
        doc.add_paragraph()

    fields = [
        ("学       院", meta.get("department", "")),
        ("专       业", meta.get("major", "")),
        ("学       号", meta.get("student_id", "")),
        ("学 生 姓 名", meta.get("author", "")),
        ("指 导 教 师", meta.get("advisor", "")),
    ]
    for label, value in fields:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"{label}：")
        set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 14, bold=True)
        run2 = p.add_run(str(value))
        set_run_cjk_font(run2, FONT_BODY_ZH, FONT_BODY_EN, 14, bold=False)
        pPr = p._element.get_or_add_pPr()
        spacing = pPr.find(_qn("w:spacing"))
        if spacing is None:
            spacing = OxmlElement("w:spacing"); pPr.append(spacing)
        spacing.set(_qn("w:line"), str(int(240 * 2.0)))
        spacing.set(_qn("w:lineRule"), "auto")

    for _ in range(4):
        doc.add_paragraph()

    now = datetime.now()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"{now.year} 年 {now.month} 月")
    set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 14, bold=False)


# -------------------- Abstract --------------------

def parse_abstract(md_text):
    """Parse drafts/00-abstract.md into zh and en blocks.

    Accepts either H1 ('# 摘要' / '# Abstract') or H2 ('## 中文摘要' / '## 英文摘要')
    as section anchors. Extracts trailing keyword line.
    """
    body = strip_front_matter(md_text)
    lines = body.splitlines()
    sections = {"zh": [], "en": []}
    cur = None
    zh_anchors = (
        re.compile(r"^#+\s*(摘\s*要|中文摘要)\s*$"),
    )
    en_anchors = (
        re.compile(r"^#+\s*(英文摘要|Abstract)\s*$", re.IGNORECASE),
    )
    for line in lines:
        if any(p.match(line) for p in zh_anchors):
            cur = "zh"; continue
        if any(p.match(line) for p in en_anchors):
            cur = "en"; continue
        if cur is None:
            continue
        sections[cur].append(line)

    def extract(block, key_patterns):
        text = "\n".join(block).strip()
        kw = None
        for pat in key_patterns:
            m = re.search(pat, text, re.MULTILINE)
            if m:
                kw = m.group(1).strip()
                text = (text[:m.start()] + text[m.end():]).strip()
                break
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return {"paragraphs": paragraphs, "keywords": kw}

    return {
        "zh": extract(sections["zh"], [
            "^\\**关键词\\**\\s*[:\uff1a](.+)$",
        ]),
        "en": extract(sections["en"], [
            "(?im)^\\**Key\\s*words?\\**\\s*[:\uff1a](.+)$",
            "(?im)^\\**Keywords\\**\\s*[:\uff1a](.+)$",
        ]),
    }


def render_abstract(doc, abstract, title_zh, title_en=None):
    add_heading_1(doc, "摘    要", page_break=False)
    for p in abstract["zh"]["paragraphs"]:
        add_body_paragraph(doc, p)
    if abstract["zh"]["keywords"]:
        par = doc.add_paragraph()
        set_par_line_spacing(par, 1.5)
        set_first_line_indent_chars(par, 2)
        run = par.add_run("关键词：")
        set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 12, bold=True)
        run2 = par.add_run(abstract["zh"]["keywords"])
        set_run_cjk_font(run2, FONT_BODY_ZH, FONT_BODY_EN, 12, bold=False)

    add_heading_1(doc, "ABSTRACT", page_break=True)
    for p in abstract["en"]["paragraphs"]:
        add_body_paragraph(doc, p)
    if abstract["en"]["keywords"]:
        par = doc.add_paragraph()
        set_par_line_spacing(par, 1.5)
        set_first_line_indent_chars(par, 2)
        run = par.add_run("Keywords: ")
        set_run_cjk_font(run, FONT_HEAD_ZH, FONT_BODY_EN, 12, bold=True)
        run2 = par.add_run(abstract["en"]["keywords"])
        set_run_cjk_font(run2, FONT_BODY_ZH, FONT_BODY_EN, 12, bold=False)


# -------------------- TOC --------------------

def render_toc(doc, levels=3):
    add_heading_1(doc, "目    录", page_break=True)
    p = doc.add_paragraph()
    add_toc_field(p, levels=levels)


# -------------------- References --------------------

def format_gbt7714(entry, idx):
    """Format a reference in GB/T 7714-2015 numeric style.

    Supports 6 literature types per the national standard:
      [J] journal  [M] monograph/book  [C] conference  [D] dissertation
      [P] patent  [S] standard

    Key format differences:
      Journal:  作者. 题名[J]. 刊名, 年, 卷(期): 起页-止页.
      Book:     作者. 书名[M]. 出版地: 出版社, 年.
      Conference:作者. 题名[C]. 出版地: 出版社, 年: 起页-止页.
      Thesis:   作者. 题名[D]. 保存地: 保存单位, 年.
      Patent:   申请者. 题名: 国别, 专利号[P]. 公告日期.
      Standard: 起草者. 标准代号 名称[S]. 出版地: 出版社, 年.
    """
    def _authors_str(authors, lang="zh"):
        """Format author list: 3 or fewer=all, more=first 3 + et al/等."""
        if not authors:
            return ""
        names = []
        for a in authors:
            if isinstance(a, str):
                names.append(a.strip())
            elif isinstance(a, dict):
                n = " ".join([x for x in [a.get("given"), a.get("family")] if x])
                names.append(n.strip())
        names = [n for n in names if n]
        if not names:
            return ""
        if len(names) <= 3:
            return ", ".join(names)
        suffix = "等" if lang == "zh" else ", et al"
        return ", ".join(names[:3]) + suffix

    lang = "zh" if entry.get("language") == "zh" else "en"
    ref_type = entry.get("type", "journal")
    authors = entry.get("authors") or []
    title = (entry.get("title") or "").strip().rstrip(".")
    year = entry.get("year")
    doi = entry.get("doi") or ""
    url = entry.get("url") or ""

    author_str = _authors_str(authors, lang)

    # ── Type-specific formatting ──────────────────────────

    if ref_type == "journal":
        # [J] 作者. 题名[J]. 刊名, 年, 卷(期): 起页-止页.
        venue = entry.get("venue") or entry.get("journal") or ""
        volume = entry.get("volume")
        issue = entry.get("issue")
        pages = entry.get("pages")

        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}[J].")

        journal_meta = venue if venue else ""
        if year:
            journal_meta += f", {year}"
        if volume:
            vol_str = str(volume)
            if issue:
                vol_str += f"({issue})"
            if pages:
                vol_str += f": {pages}"
            elif issue:
                pass  # just volume(issue)
            journal_meta += f", {vol_str}"
        elif issue:
            journal_meta += f", ({issue})"
            if pages:
                journal_meta += f": {pages}"
        elif pages:
            journal_meta += f": {pages}"

        if journal_meta:
            parts.append(journal_meta + ".")

    elif ref_type in ("book", "monograph"):
        # [M] 作者. 书名[M]. 出版地: 出版社, 年.
        publisher = entry.get("publisher") or entry.get("venue") or ""
        pub_place = entry.get("pub_place") or ""

        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}[M].")
        pub_str = ""
        if pub_place:
            pub_str += pub_place
        if publisher:
            pub_str += (": " if pub_place else "") + publisher
        if year:
            pub_str += f", {year}"
        if pub_str:
            parts.append(pub_str + ".")

    elif ref_type == "conference":
        # [C] 作者. 题名[C]. 出版地: 出版社, 年: 起页-止页.
        publisher = entry.get("publisher") or ""
        pub_place = entry.get("pub_place") or ""
        pages = entry.get("pages")
        booktitle = entry.get("booktitle") or entry.get("venue") or ""
        editors = entry.get("editors") or []
        editors_str = _authors_str(editors, lang) if editors else ""

        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}[C].")
        if editors_str or booktitle:
            in_part = "In:"
            if editors_str:
                in_part += f" {editors_str}"
                if lang == "en":
                    in_part += ", eds."
            if booktitle:
                in_part += f" {booktitle}."
            elif not in_part.endswith("."):
                in_part += "."
            parts.append(in_part)
        pub_str = ""
        if pub_place:
            pub_str += pub_place
        if publisher:
            pub_str += (": " if pub_place else "") + publisher
        if year:
            pub_str += f", {year}"
        if pages:
            pub_str += f": {pages}"
        if pub_str:
            parts.append(pub_str + ".")

    elif ref_type == "thesis":
        # [D] 作者. 题名[D]. 保存地: 保存单位, 年.
        school = entry.get("school") or entry.get("publisher") or entry.get("venue") or ""
        place = entry.get("pub_place") or ""

        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}[D].")
        loc_str = ""
        if place:
            loc_str += place
        if school:
            loc_str += (": " if place else "") + school
        if year:
            loc_str += f", {year}"
        if loc_str:
            parts.append(loc_str + ".")

    elif ref_type == "patent":
        # [P] 申请者. 题名: 国别, 专利号[P]. 日期.
        patent_number = entry.get("patent_number") or entry.get("doi") or ""
        country = entry.get("pub_place") or entry.get("country") or ""
        pub_date = entry.get("pub_date") or (str(year) if year else "")

        parts = []
        if author_str:
            parts.append(author_str + ".")
        patent_title = f"{title}"
        if country or patent_number:
            patent_title += ": "
            if country:
                patent_title += country
            if patent_number:
                patent_title += (", " if country else "") + patent_number
        parts.append(f"{patent_title}[P].")
        if pub_date:
            parts.append(pub_date + ".")

    elif ref_type == "standard":
        # [S] 起草者. 标准代号 名称[S]. 出版地: 出版社, 年.
        std_code = entry.get("std_code") or ""
        publisher = entry.get("publisher") or entry.get("venue") or ""
        pub_place = entry.get("pub_place") or ""

        parts = []
        if author_str:
            parts.append(author_str + ".")
        std_title = std_code + " " + title if std_code else title
        parts.append(f"{std_title}[S].")
        pub_str = ""
        if pub_place:
            pub_str += pub_place
        if publisher:
            pub_str += (": " if pub_place else "") + publisher
        if year:
            pub_str += f", {year}"
        if pub_str:
            parts.append(pub_str + ".")

    elif ref_type == "preprint" or ref_type == "web":
        # [EB/OL] or [J/OL] 作者. 题名[J/OL]. 刊名, 年[引用日期]. URL.
        venue = entry.get("venue") or entry.get("journal") or ""
        tag = "[J/OL]" if entry.get("doi") else "[EB/OL]"

        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}{tag}.")
        if venue:
            parts[-1] = parts[-1].rstrip(".") + f" {venue}."
        if year:
            parts.append(f"{year}.")
        if url:
            parts.append(url + ".")

    else:
        # Generic fallback
        venue = entry.get("venue") or entry.get("journal") or entry.get("publisher") or ""
        volume = entry.get("volume")
        issue = entry.get("issue")
        pages = entry.get("pages")

        tag = "[J]"
        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}{tag}.")
        meta = venue if venue else ""
        if year:
            meta += (", " if venue else "") + str(year)
        if volume:
            vol_str = str(volume)
            if issue:
                vol_str += f"({issue})"
            if pages:
                vol_str += f": {pages}"
            meta += f", {vol_str}"
        if meta:
            parts.append(meta + ".")

    # ── DOI / URL postfix (all types) ────────────────────
    if doi and "DOI:" not in " ".join(parts):
        parts.append(f"DOI:{doi}.")
    elif url and not doi:
        parts.append(f"{url}.")

    text = " ".join(parts).strip()
    # Clean up double periods
    text = re.sub(r"\.\s*\.", ".", text)
    return f"[{idx}] {text}"


def render_references(doc, order_keys, library_meta):
    add_heading_1(doc, "参考文献", page_break=True)
    by_key = {e.get("cite_key") or e.get("id") or e.get("key"): e for e in library_meta}
    for idx, key in enumerate(order_keys, start=1):
        entry = by_key.get(key, {"title": key})
        text = format_gbt7714(entry, idx)
        par = doc.add_paragraph()
        pPr = par._element.get_or_add_pPr()
        ind = pPr.find(_qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind"); pPr.append(ind)
        ind.set(_qn("w:left"), "480")
        ind.set(_qn("w:hanging"), "480")
        spacing = pPr.find(_qn("w:spacing"))
        if spacing is None:
            spacing = OxmlElement("w:spacing"); pPr.append(spacing)
        spacing.set(_qn("w:line"), str(int(240 * 1.5)))
        spacing.set(_qn("w:lineRule"), "auto")
        run = par.add_run(text)
        set_run_cjk_font(run, FONT_BODY_ZH, FONT_BODY_EN, 10.5, bold=False)


# -------------------- Main --------------------

def main():
    thesis = load_thesis_json(os.path.join(ROOT, "thesis.json"))
    contract = json.load(open(os.path.join(ROOT, "template", "format-contract.json"),
                              "r", encoding="utf-8"))
    library = json.load(open(os.path.join(ROOT, "library", "metadata.json"),
                             "r", encoding="utf-8"))
    if isinstance(library, dict) and "entries" in library:
        library = library["entries"]

    outline = thesis["outline"]
    draft_texts = {}
    for ch in outline:
        dp = os.path.join(ROOT, ch["draft_path"])
        if os.path.exists(dp):
            draft_texts[ch["id"]] = open(dp, "r", encoding="utf-8").read()
        else:
            draft_texts[ch["id"]] = ""

    body_chapters = [ch for ch in outline if ch["id"] not in ("ch0",)]
    body_texts = [draft_texts[ch["id"]] for ch in body_chapters]
    abstract_text = draft_texts.get("ch0", "")

    cite_index, _ = build_citation_index([abstract_text] + body_texts)
    order_keys = sorted(cite_index.keys(), key=lambda k: cite_index[k])

    drafts_seq = [(i + 1, body_texts[i]) for i in range(len(body_texts))]
    fig_map, tbl_map = build_asset_numbers(drafts_seq)
    assets = load_asset_manifest()

    doc = Document()
    enable_update_fields_on_open(doc)

    style = doc.styles["Normal"]
    style.font.name = FONT_BODY_EN
    style.font.size = Pt(12)
    rpr = style.element.get_or_add_rPr()
    rFonts = rpr.find(_qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rpr.append(rFonts)
    rFonts.set(_qn("w:ascii"), FONT_BODY_EN)
    rFonts.set(_qn("w:hAnsi"), FONT_BODY_EN)
    rFonts.set(_qn("w:eastAsia"), FONT_BODY_ZH)

    s0 = doc.sections[0]
    setup_page_margins(s0, contract)
    set_title_pg(s0)
    clear_header(s0)
    clear_footer(s0)

    render_cover(doc, thesis["meta"])

    doc.add_section(WD_SECTION.NEW_PAGE)
    s1 = doc.sections[1]
    setup_page_margins(s1, contract)
    unset_title_pg(s1)
    s1.header.is_linked_to_previous = False
    s1.footer.is_linked_to_previous = False
    clear_header(s1)
    set_footer_page_number(s1, roman=True)
    configure_section_pg_num(s1, fmt="upperRoman", start=1)

    if abstract_text:
        abs_parsed = parse_abstract(abstract_text)
        render_abstract(doc, abs_parsed, thesis["meta"]["title"])

    render_toc(doc, levels=contract.get("front_matter", {}).get("toc", {}).get("levels", 3))

    doc.add_section(WD_SECTION.NEW_PAGE)
    s2 = doc.sections[2]
    setup_page_margins(s2, contract)
    unset_title_pg(s2)
    s2.header.is_linked_to_previous = False
    s2.footer.is_linked_to_previous = False
    set_header_text(s2, f"{thesis['meta']['school']} · {thesis['meta']['title']}", with_border=True)
    footer_pattern = contract.get("header_footer", {}).get("body_footer_pattern",
                                                           "第 {PAGE} 页 共 {NUMPAGES} 页")
    set_footer_page_number(s2, pattern=footer_pattern)
    configure_section_pg_num(s2, fmt="decimal", start=1)

    rendered_figs = set()
    rendered_tbls = set()
    for idx, ch in enumerate(body_chapters):
        page_break = (idx > 0)
        render_chapter(
            doc, draft_texts[ch["id"]], cite_index, fig_map, tbl_map,
            assets, rendered_figs, rendered_tbls,
            page_break_on_h1=page_break, emit_h1=True,
        )

    render_references(doc, order_keys, library)

    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "thesis.docx")
    doc.save(out_path)

    figs_used = len(rendered_figs)
    tbls_used = len(rendered_tbls)
    refs = len(order_keys)
    print(f"[ok] rendered: chapters={len(body_chapters)} figures={figs_used} "
          f"tables={tbls_used} references={refs}")
    print(f"[ok] saved: {out_path} ({os.path.getsize(out_path)} bytes)")

    thesis["progress"]["last_updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    thesis["progress"].setdefault("notes", []).append(
        f"排版重制完成: figures={figs_used} tables={tbls_used} refs={refs}, "
        f"已实现封面/目录/罗马-阿拉伯分页码/页眉页脚/字体规范."
    )
    thesis["assets"]["figure_count"] = sum(1 for a in assets.values() if a.get("type") == "figure")
    thesis["assets"]["table_count"] = sum(1 for a in assets.values() if a.get("type") == "table")
    json.dump(thesis, open(os.path.join(ROOT, "thesis.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
