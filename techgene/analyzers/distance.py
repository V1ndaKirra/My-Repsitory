"""维度五：产业接口距离

衡量从论文到第一个可部署产品需要多少中间步骤。

数据源：
- GitHub 首次提交时间（相对于论文发表日期）
- HuggingFace 模型上传时间
- 开源实现的存在性

评分逻辑：
- 论文发表 1 个月内出现开源实现 → 5 分（距离极短）
- 3-6 个月 → 4 分
- 6-12 个月 → 3 分
- 1-2 年 → 2 分
- 2 年以上/无实现 → 1 分
"""

from datetime import datetime, timedelta
from loguru import logger

from .base import BaseAnalyzer


class DistanceAnalyzer(BaseAnalyzer):
    dimension = "distance"

    def analyze(self, paper: dict) -> dict:
        """分析论文的产业接口距离。"""
        title = paper.get("title", "")
        published_str = paper.get("published", "")

        # 解析出版日期
        pub_date = None
        if published_str:
            try:
                pub_date = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        if not pub_date:
            # 无法解析日期，默认中等距离
            return {
                "score": 2.5,
                "confidence": 0.2,
                "evidence": {"reason": "unknown_publish_date"},
            }

        # 计算距离（论文至今的天数）
        days_since = (datetime.utcnow() - pub_date.replace(tzinfo=None)).days

        # 检查开源实现存在性
        has_implementation = self._check_implementation(title)

        # 基于时间 + 实现存在性打分
        if has_implementation:
            if days_since <= 90:
                score = 5.0
            elif days_since <= 180:
                score = 4.0
            elif days_since <= 365:
                score = 3.5
            elif days_since <= 730:
                score = 2.5
            else:
                score = 2.0
        else:
            # 无开源实现，距离远
            if days_since <= 30:
                score = 3.0  # 太新，还没人实现是正常的
            elif days_since <= 180:
                score = 2.0
            else:
                score = 1.0  # 半年了还没人实现 → 产业距离大

        score = self.clamp(score)
        confidence = 0.5 if has_implementation else 0.3

        evidence = {
            "days_since_published": days_since,
            "has_implementation": has_implementation,
            "published_date": published_str[:10] if published_str else "N/A",
        }

        logger.debug(
            f"产业距离: {title[:40]} → {score:.1f} "
            f"(days={days_since}, impl={has_implementation})"
        )

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _check_implementation(self, title: str) -> bool:
        """检查是否有开源实现（通过 GitHub 搜索）。"""
        import httpx

        keywords = self._extract_keywords(title)
        if not keywords:
            return False

        query = " ".join(keywords[:3])
        try:
            resp = httpx.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} in:name,description",
                    "per_page": 1,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=8.0,
            )
            return resp.status_code == 200 and resp.json().get("total_count", 0) > 0
        except Exception:
            return False

    def _extract_keywords(self, title: str) -> list[str]:
        import re
        stopwords = {"a", "an", "the", "for", "and", "of", "in", "to", "with",
                     "on", "is", "are", "by", "as", "at", "or", "from",
                     "learning", "model", "approach", "method", "new"}
        words = re.findall(r"[a-zA-Z0-9]+", title.lower())
        return [w for w in words if w not in stopwords and len(w) > 2][:4]
