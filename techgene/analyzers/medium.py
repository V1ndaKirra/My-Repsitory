"""维度六：扩散媒介

衡量技术通过哪些渠道传播，覆盖了哪些人群。

五个媒介通道：
- 论文引用 (academic)    → 研究者
- GitHub stars (developer) → 开发者
- HuggingFace (practitioner) → 应用开发者
- 产品/API (commercial)     → 最终用户
- 媒体/社交 (public)        → 公众

评分逻辑：
  每个通道 0-1 分，加权求和后映射到 1-5。
  权重：academic=0.15, developer=0.35, practitioner=0.25, commercial=0.15, public=0.10
"""

import httpx
from datetime import datetime, timedelta
from loguru import logger

from .base import BaseAnalyzer

GITHUB_API = "https://api.github.com"
CHANNELS = ["academic", "developer", "practitioner", "commercial", "public"]

# 通道权重
WEIGHTS = {
    "academic": 0.15,
    "developer": 0.35,
    "practitioner": 0.25,
    "commercial": 0.15,
    "public": 0.10,
}


class MediumAnalyzer(BaseAnalyzer):
    dimension = "medium"

    def analyze(self, paper: dict) -> dict:
        """分析论文的扩散媒介覆盖度。"""
        title = paper.get("title", "")
        arxiv_id = paper.get("arxiv_id", "")

        channel_scores = {}

        # 1. 学术通道：有引用即得分（论文发表就有学术传播）
        citation_count = paper.get("citation_count", 0)
        if citation_count > 0:
            channel_scores["academic"] = min(1.0, citation_count / 1000)
        else:
            channel_scores["academic"] = 0.1  # 新论文也有基础学术传播

        # 2. 开发者通道：查 GitHub 是否有相关仓库
        channel_scores["developer"] = self._check_github_channel(title, arxiv_id)

        # 3. 应用开发者通道：暂留（后续加 HuggingFace API）
        channel_scores["practitioner"] = 0.0

        # 4. 商业通道：暂留（后续加产品检测）
        channel_scores["commercial"] = 0.0

        # 5. 公众通道：暂留（后续加媒体/社交检测）
        channel_scores["public"] = 0.0

        # 加权合成
        weighted = sum(channel_scores.get(ch, 0) * WEIGHTS.get(ch, 0) for ch in CHANNELS)
        # 映射到 1-5
        score = self.clamp(1.0 + weighted * 4.0)

        # 置信度：已实现的通道越多，置信度越高
        active_channels = sum(1 for v in channel_scores.values() if v > 0)
        confidence = min(1.0, active_channels / 3.0)

        evidence = {
            "channel_scores": channel_scores,
            "citation_count": citation_count,
            "active_channels": active_channels,
        }

        logger.debug(
            f"扩散媒介: {title[:40]}... → {score:.1f} "
            f"(channels: {active_channels}/5, developer={channel_scores['developer']:.2f})"
        )

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _check_github_channel(self, title: str, arxiv_id: str) -> float:
        """检查 GitHub 上是否有相关仓库。

        搜索策略：
        1. 先按论文标题的关键词搜索
        2. 如果有结果，取 stars 最高的仓库
        3. 根据 star 数量打分
        """
        # 提取标题中的关键词（取前3个有意义词）
        keywords = self._extract_keywords(title)

        if not keywords:
            return 0.0

        query = " ".join(keywords[:4])
        try:
            resp = httpx.get(
                f"{GITHUB_API}/search/repositories",
                params={
                    "q": f"{query} in:name,description",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 3,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
            )

            if resp.status_code == 403:
                # GitHub API 限速
                logger.warning("GitHub API 403 限速，跳过开发者通道")
                return 0.0

            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])

            if not items:
                return 0.0

            # 取最匹配的仓库
            top_repo = items[0]
            stars = top_repo.get("stargazers_count", 0)
            repo_name = top_repo.get("full_name", "")

            # 按 star 数打分
            if stars >= 50000:
                score = 1.0
            elif stars >= 10000:
                score = 0.8
            elif stars >= 1000:
                score = 0.5
            elif stars >= 100:
                score = 0.3
            elif stars >= 10:
                score = 0.15
            else:
                score = 0.05

            logger.debug(f"  GitHub: {repo_name} ({stars}★) → {score:.2f}")

            return score

        except httpx.HTTPError as e:
            logger.debug(f"  GitHub 查询失败: {e}")
            return 0.0
        except Exception as e:
            logger.debug(f"  GitHub 异常: {e}")
            return 0.0

    def _extract_keywords(self, title: str) -> list[str]:
        """从标题提取关键词。"""
        # 去除常见停用词和标点
        stopwords = {
            "a", "an", "the", "for", "and", "of", "in", "to", "with",
            "on", "is", "are", "by", "as", "at", "or", "from", "its",
            "via", "into", "over", "new", "based", "using", "towards",
            "learning", "model", "models", "approach", "method", "toward",
        }
        import re

        words = re.findall(r"[a-zA-Z0-9]+", title.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords[:6]  # 最多取6个关键词
