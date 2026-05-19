"""维度七：垂直迭代潜力

衡量技术能否在同一范式内持续进化（v1 → v2 → v3...）。

数据源：
- arXiv 搜索后续改进论文
- GitHub release 频率
- 后续工作的数量

评分逻辑：
- 有明确的 v2/v3 系列 → 5 分
- 有大量改进论文 → 4 分
- 有一定后续工作 → 3 分
- 孤立的一次性工作 → 1-2 分
"""

import httpx
from loguru import logger

from .base import BaseAnalyzer


class IterationAnalyzer(BaseAnalyzer):
    dimension = "iteration"

    def analyze(self, paper: dict) -> dict:
        """分析论文的垂直迭代潜力。"""
        title = paper.get("title", "")

        # 1. 检查标题是否有版本号信号（v2, improved, enhanced 等）
        version_signal = self._check_version_pattern(title.lower())

        # 2. arXiv 搜索后续改进论文
        followup_count = self._search_followups(title)

        # 3. 核心思想的简单性（越简单越容易迭代）
        simplicity = self._estimate_simplicity(title.lower())

        # 合成分数
        if version_signal:
            base_score = 5.0
        elif followup_count >= 10:
            base_score = 4.5
        elif followup_count >= 5:
            base_score = 4.0
        elif followup_count >= 2:
            base_score = 3.0
        else:
            base_score = 2.0

        # 简单性奖励
        simplicity_bonus = simplicity * 0.5
        score = self.clamp(base_score + simplicity_bonus)

        confidence = 0.6 if followup_count > 0 else 0.3

        evidence = {
            "has_version_pattern": version_signal,
            "followup_count": followup_count,
            "simplicity_estimate": simplicity,
        }

        logger.debug(
            f"迭代潜力: {title[:40]} → {score:.1f} "
            f"(v_pattern={version_signal}, followups={followup_count})"
        )

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _check_version_pattern(self, title: str) -> bool:
        """检查标题中是否有版本迭代信号。"""
        import re

        patterns = [
            r"\bv\d+\b",           # v2, v3, v10
            r"\bversion\s*\d+",    # version 2
            r"\bpart\s*[ivx]+",    # part II, III
            r"\bimproved\b",       # improved X
            r"\benhanced\b",       # enhanced X
            r"revisited",          # X revisited
            r"rethinking",         # rethinking X
        ]
        return any(re.search(p, title) for p in patterns)

    def _search_followups(self, title: str) -> int:
        """在 arXiv 搜索后续改进论文。"""
        keywords = self._extract_keywords(title)
        if not keywords:
            return 0

        # 用核心关键词搜索
        core_term = keywords[0]
        query = f"all:{core_term}"

        try:
            resp = httpx.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": query,
                    "max_results": 5,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
                timeout=10.0,
                headers={"User-Agent": "TechGene/0.1"},
            )

            if resp.status_code != 200:
                return 0

            # 简单计数（实际应解析 XML）
            import re
            entries = len(re.findall(r"<entry>", resp.text))
            return entries

        except Exception as e:
            logger.debug(f"arXiv followup 搜索失败: {e}")
            return 0

    def _estimate_simplicity(self, title: str) -> float:
        """估算核心思想的简单性。

        简单思想更容易被迭代（如 Attention、Residual Connection）。
        信号：标题中是否有 "simple", "unified", "efficient", "minimal" 等词。
        """
        simple_words = [
            "simple", "unified", "efficient", "minimal", "all you need",
            "one shot", "end-to-end", "single", "just",
        ]
        hits = sum(1 for w in simple_words if w in title)
        return min(1.0, hits * 0.25)

    def _extract_keywords(self, title: str) -> list[str]:
        import re
        stopwords = {"a", "an", "the", "for", "and", "of", "in", "to", "with",
                     "on", "is", "are", "by", "as", "at", "or", "from",
                     "learning", "model", "approach", "method", "new", "using"}
        words = re.findall(r"[a-zA-Z0-9]+", title.lower())
        return [w for w in words if w not in stopwords and len(w) > 3][:3]
