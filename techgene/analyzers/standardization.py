"""维度四：标准化效应

衡量技术是否创造了公共竞技场（基准测试、竞赛、统一评估标准）。

数据源：Papers With Code API（检查关联的 benchmark）
"""

import httpx
from loguru import logger

from .base import BaseAnalyzer

PWC_API = "https://paperswithcode.com/api/v1"


class StandardizationAnalyzer(BaseAnalyzer):
    dimension = "standardization"

    def analyze(self, paper: dict) -> dict:
        """分析论文的标准化效应。"""
        title = paper.get("title", "")

        # 搜索 Papers With Code
        benchmark_count = self._search_benchmarks(title)

        # 关键词检测（benchmark/dataset/standard 等出现在标题中）
        kw_score = self._keyword_signal(title.lower())

        # 合成分数
        if benchmark_count >= 5:
            score = 5.0
        elif benchmark_count >= 2:
            score = min(5.0, 2.0 + benchmark_count * 0.5)
        elif benchmark_count == 1:
            score = 2.5
        else:
            score = 1.0 + kw_score  # 关键词是弱信号

        score = self.clamp(score)
        confidence = 0.5 if benchmark_count > 0 else 0.2

        evidence = {
            "benchmark_count": benchmark_count,
            "keyword_signal": kw_score,
        }

        logger.debug(
            f"标准化效应: {title[:40]} → {score:.1f} (benchmarks={benchmark_count})"
        )

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _search_benchmarks(self, title: str) -> int:
        """在 Papers With Code 搜索相关 benchmark。"""
        keywords = self._extract_keywords(title)
        if not keywords:
            return 0

        query = "+".join(keywords[:3])
        try:
            resp = httpx.get(
                f"{PWC_API}/papers/",
                params={"q": query, "items_per_page": 5},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return 0

            data = resp.json()
            count = data.get("count", 0)
            return min(count, 10)  # 上限 10

        except Exception as e:
            logger.debug(f"PWC 查询失败: {e}")
            return 0

    def _keyword_signal(self, text: str) -> float:
        """基于关键词的标准化信号。"""
        signals = [
            "benchmark", "leaderboard", "competition", "challenge",
            "standard", "evaluation protocol", "dataset for",
        ]
        hits = sum(1 for s in signals if s in text)
        return min(1.5, hits * 0.5)

    def _extract_keywords(self, title: str) -> list[str]:
        import re
        stopwords = {"a", "an", "the", "for", "and", "of", "in", "to", "with",
                     "on", "is", "are", "by", "as", "at", "or", "from",
                     "learning", "model", "models", "approach", "method"}
        words = re.findall(r"[a-zA-Z0-9]+", title.lower())
        return [w for w in words if w not in stopwords and len(w) > 2][:5]
