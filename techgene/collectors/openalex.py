"""OpenAlex API 采集器

替代 arXiv API 作为主要论文发现渠道。
OpenAlex 免费额度: 10 万次/天，远高于 arXiv。
"""

import httpx
from datetime import date, timedelta
from loguru import logger
from typing import Optional

OPENALEX_API = "https://api.openalex.org/works"


def fetch_new_papers(
    target_date: Optional[date] = None,
    max_results: int = 100,
) -> list[dict]:
    """通过 OpenAlex 获取指定日期发表的 CS 相关新论文。

    OpenAlex 按 publication_date 过滤，用 concepts 限定 AI/ML/CV/NLP 领域。

    Args:
        target_date: 目标日期，默认昨天
        max_results: 最多返回数量

    Returns:
        论文列表，每篇含统一格式字段
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.isoformat()

    # OpenAlex concepts for CS subfields
    # cs.AI: C154945302 (Artificial Intelligence)
    # cs.CL: C204321447 (Natural Language Processing)
    # cs.CV: C31972630 (Computer Vision)
    # cs.LG: C119857082 (Machine Learning)
    cs_concepts = "C154945302|C204321447|C31972630|C119857082"

    # 限定 arXiv 来源 + CS 概念 + 指定日期
    filter_str = (
        f"primary_location.source.id:S4306400194,"  # arXiv (Cornell University)
        f"publication_date:{date_str},"
        f"concepts.id:{cs_concepts}"
    )

    params = {
        "filter": filter_str,
        "sort": "cited_by_count:desc",
        "per_page": min(max_results, 200),
        "select": "id,doi,title,publication_date,authorships,abstract_inverted_index,primary_location,concepts,cited_by_count",
        "mailto": "hanako@example.com",
    }

    logger.info(f"OpenAlex 查询: {date_str}, 最多 {max_results} 篇")

    all_papers = []
    page = 1

    while len(all_papers) < max_results:
        try:
            resp = httpx.get(
                OPENALEX_API,
                params={**params, "page": page, "per_page": min(max_results - len(all_papers), 200)},
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"OpenAlex API 请求失败: {e}")
            break

        data = resp.json()
        results = data.get("results", [])

        for work in results:
            paper = _parse_work(work)
            if paper:
                all_papers.append(paper)

        # 检查是否还有更多页
        if len(results) < params["per_page"] or len(all_papers) >= max_results:
            break
        page += 1

    logger.info(f"OpenAlex 返回 {len(all_papers)} 篇论文")
    return all_papers


def _parse_work(work: dict) -> dict | None:
    """将 OpenAlex work 转为统一格式。"""
    try:
        work_id = work.get("id", "")
        # 提取 arXiv ID
        arxiv_id = None
        primary = work.get("primary_location") or {}
        if primary.get("source", {}).get("display_name") == "arXiv":
            landing = primary.get("landing_page_url", "")
            if "arxiv.org/abs/" in landing:
                arxiv_id = landing.split("arxiv.org/abs/")[-1].rstrip("/").split("v")[0]

        if not arxiv_id:
            # 如果没有 arXiv ID，用 OpenAlex ID 代替
            arxiv_id = work_id.split("/")[-1] if work_id else None

        if not arxiv_id:
            return None

        # 还原 inverted abstract
        abstract = ""
        inv = work.get("abstract_inverted_index")
        if inv:
            words = [""] * (max(max(idx) for idx in inv.values()) + 1)
            for word, positions in inv.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join(words)

        # 作者
        authors = []
        for a in work.get("authorships", [])[:10]:
            name = a.get("author", {}).get("display_name", "")
            if name:
                authors.append(name)

        # 概念标签
        concepts = []
        for c in work.get("concepts", [])[:10]:
            concepts.append(
                {
                    "display_name": c.get("display_name", ""),
                    "level": c.get("level", 0),
                    "score": c.get("score", 0),
                }
            )

        # 日期
        pub_date = work.get("publication_date", "")

        return {
            "arxiv_id": arxiv_id,
            "title": work.get("title", ""),
            "authors": authors,
            "abstract": abstract,
            "published": pub_date,
            "categories": [],
            "pdf_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "source": "openalex",
            "concepts": concepts,
            "citation_count": work.get("cited_by_count", 0),
            "openalex_id": work_id,
        }
    except Exception as e:
        logger.debug(f"解析 work 失败: {e}")
        return None
