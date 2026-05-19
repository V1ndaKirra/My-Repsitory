"""arXiv API 采集器

查询指定日期范围的 CS 分类新论文，返回结构化数据。
arXiv API 文档: https://info.arxiv.org/help/api/
"""

import httpx
from datetime import date, timedelta
from lxml import etree
from loguru import logger
from typing import Optional

ARXIV_API = "https://export.arxiv.org/api/query"
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def fetch_new_papers(
    target_date: Optional[date] = None,
    categories: str = "cs.AI",
    max_results: int = 100,
) -> list[dict]:
    """获取指定日期 arXiv CS 分类的新论文。

    arXiv 的 submittedDate 过滤会导致服务端查询超时，
    因此改为获取最近论文后在 Python 中按 published 日期筛选。

    Args:
        target_date: 目标日期，默认昨天
        categories: 单个 CS 子分类
        max_results: arXiv 返回的最大结果数（实际可能更多用于筛选）

    Returns:
        符合目标日期的论文列表
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    query = f"cat:{categories}"
    params = {
        "search_query": query,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    logger.info(f"查询 arXiv: {categories}, 目标日期 {target_date}, 最多 {max_results} 篇")

    try:
        resp = httpx.get(
            ARXIV_API,
            params=params,
            timeout=20.0,
            headers={"User-Agent": "TechGene/0.1 (mailto:hanako@example.com)"},
        )

        if resp.status_code == 429:
            import time
            logger.warning("arXiv 429 限速，等待 60 秒重试...")
            time.sleep(60)
            resp = httpx.get(
                ARXIV_API,
                params=params,
                timeout=20.0,
                headers={"User-Agent": "TechGene/0.1 (mailto:hanako@example.com)"},
            )

        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"arXiv API 请求失败: {e}")
        return []

    all_papers = _parse_response(resp.text)

    # 在 Python 中按 published 日期筛选
    target_str = target_date.isoformat()
    filtered = [p for p in all_papers if (p.get("published") or "").startswith(target_str)]
    logger.info(f"arXiv 返回 {len(all_papers)} 篇，匹配目标日期 {target_date}: {len(filtered)} 篇")
    return filtered


def _parse_response(xml_text: str) -> list[dict]:
    """解析 arXiv Atom XML 响应。"""
    root = etree.fromstring(xml_text.encode("utf-8"))
    entries = root.findall("atom:entry", NAMESPACES)

    papers = []
    for entry in entries:
        arxiv_id = _extract_text(entry, "atom:id")
        # arXiv ID 格式: http://arxiv.org/abs/2405.12345v1
        if arxiv_id:
            arxiv_id = arxiv_id.split("/abs/")[-1]

        categories = [
            cat.get("term")
            for cat in entry.findall("atom:category", NAMESPACES)
            if cat.get("scheme") == "http://arxiv.org/schemas/atom"
        ]

        authors = [
            author.find("atom:name", NAMESPACES).text
            for author in entry.findall("atom:author", NAMESPACES)
            if author.find("atom:name", NAMESPACES) is not None
        ]

        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": _extract_text(entry, "atom:title"),
                "authors": authors,
                "abstract": _extract_text(entry, "atom:summary"),
                "published": _extract_text(entry, "atom:published"),
                "categories": categories,
                "pdf_url": _extract_link(entry, "related", "pdf"),
                "source": "arxiv",
            }
        )

    logger.info(f"解析完成: {len(papers)} 篇论文")
    return papers


def _extract_text(entry, tag: str) -> str:
    """提取 XML 元素的文本内容，去除多余空白。"""
    el = entry.find(f"{tag}", NAMESPACES)
    if el is None:
        return ""
    return " ".join(el.text.split()) if el.text else ""


def _extract_link(entry, rel: str, title: str = "") -> str:
    """提取指定 rel/title 的链接。"""
    for link in entry.findall("atom:link", NAMESPACES):
        if link.get("rel") == rel:
            if not title or link.get("title", "").lower() == title.lower():
                return link.get("href", "")
    return ""
