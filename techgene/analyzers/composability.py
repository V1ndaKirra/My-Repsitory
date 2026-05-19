"""维度三：可组合性

衡量技术是否可以作为模块嵌入其他系统。

数据源：
- GitHub dependents：有多少仓库依赖了这个项目
- PyPI 依赖计数（如果有）

评分逻辑：
- 大量反向依赖 → 高可组合性（被广泛作为库使用）
- 无反向依赖 → 低可组合性（可能是独立系统）
"""

import httpx
from loguru import logger

from .base import BaseAnalyzer

GITHUB_API = "https://api.github.com"


class ComposabilityAnalyzer(BaseAnalyzer):
    dimension = "composability"

    def analyze(self, paper: dict) -> dict:
        """分析论文的可组合性。"""
        title = paper.get("title", "")
        arxiv_id = paper.get("arxiv_id", "")

        # 1. 搜索 GitHub 相关仓库
        repo_full_name = self._find_repo(title)
        dependents_count = 0

        if repo_full_name:
            # 2. 获取反向依赖数
            dependents_count = self._get_dependents(repo_full_name)

        # 3. 打分
        if dependents_count >= 10000:
            base_score = 5.0
        elif dependents_count >= 1000:
            base_score = 4.0
        elif dependents_count >= 100:
            base_score = 3.0
        elif dependents_count >= 10:
            base_score = 2.0
        elif dependents_count > 0:
            base_score = 1.5
        else:
            base_score = 1.0  # 无反向依赖，默认低分

        score = self.clamp(base_score)
        confidence = 0.6 if repo_full_name else 0.3

        evidence = {
            "repo": repo_full_name or "N/A",
            "dependents_count": dependents_count,
        }

        logger.debug(
            f"可组合性: {title[:40]} → {score:.1f} "
            f"(repo={repo_full_name or 'N/A'}, dependents={dependents_count})"
        )

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _find_repo(self, title: str) -> str | None:
        """搜索论文对应的 GitHub 仓库。"""
        keywords = self._extract_keywords(title)
        if not keywords:
            return None

        query = " ".join(keywords[:4])
        try:
            resp = httpx.get(
                f"{GITHUB_API}/search/repositories",
                params={
                    "q": f"{query} in:name,description",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 1,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
            )

            if resp.status_code != 200:
                return None

            items = resp.json().get("items", [])
            if items:
                return items[0].get("full_name")
            return None

        except Exception:
            return None

    def _get_dependents(self, repo_full_name: str) -> int:
        """获取仓库的反向依赖数量。

        GitHub 不直接提供 API，用仓库的 forks 数近似，
        或用 GitHub 的 dependency graph（需要 token）。
        这里用 stars 和 forks 的加权值作为代理指标。
        """
        try:
            resp = httpx.get(
                f"{GITHUB_API}/repos/{repo_full_name}",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
            )

            if resp.status_code != 200:
                return 0

            data = resp.json()
            stars = data.get("stargazers_count", 0)
            forks = data.get("forks_count", 0)

            # forks 反映被复制/依赖的程度，比 stars 更能说明可组合性
            # 用公式: dependents ≈ forks × 2 + stars × 0.1
            estimated = forks * 2 + int(stars * 0.1)
            return estimated

        except Exception:
            return 0

    def _extract_keywords(self, title: str) -> list[str]:
        """从标题提取关键词。"""
        import re

        stopwords = {
            "a", "an", "the", "for", "and", "of", "in", "to", "with",
            "on", "is", "are", "by", "as", "at", "or", "from",
            "learning", "model", "models", "approach", "method",
            "using", "based", "new", "towards", "via",
        }
        words = re.findall(r"[a-zA-Z0-9]+", title.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords[:5]
