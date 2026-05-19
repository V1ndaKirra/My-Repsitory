"""维度一：抽象层级

衡量技术所解决问题的底层程度。
越底层的问题（如"怎么训练网络"）→ 抽象层级越高 → 潜在辐射面越广。

原理：
  1. OpenAlex concepts 的 level 值反映概念在知识树中的深度
     level=0 (如 Computer Science) → 顶层 → 问题最抽象
     level=3 (如 Object Detection)  → 深层 → 问题最具体
  2. 概念分布的香农熵反映跨领域程度
     熵越高 → 涉及的概念越分散 → 技术可能是地基型的

评分逻辑：
  抽象层级分 = 5 - (mean_level × 0.8) + (entropy × 0.3)
  clamp 到 [1.0, 5.0]
"""

import math
from dataclasses import dataclass
from loguru import logger

from .base import BaseAnalyzer


@dataclass
class ConceptInfo:
    display_name: str
    level: int
    score: float  # OpenAlex 的相关性分数 (0-1)


class AbstractionAnalyzer(BaseAnalyzer):
    dimension = "abstraction"

    def analyze(self, paper: dict) -> dict:
        """分析论文的抽象层级。"""
        concepts = paper.get("concepts", [])

        # 如果采集时已经带了 concepts，直接使用
        if concepts:
            concept_list = [
                ConceptInfo(
                    display_name=c.get("display_name", ""),
                    level=c.get("level", 0),
                    score=c.get("score", 0.0),
                )
                for c in concepts
            ]
        else:
            # 降级：无概念数据时通过其他字段估算
            logger.debug(f"论文 {paper.get('arxiv_id')} 无 concepts 数据，使用估算")
            return self._fallback_estimate(paper)

        return self._calculate(concept_list, paper)

    def _calculate(self, concepts: list[ConceptInfo], paper: dict) -> dict:
        """基于概念列表计算抽象层级分。
        
        核心思路：
        - 最低层级概念 (level 最小) 反映技术"有多底层"
        - 高层级概念占比反映技术"有多应用导向"
        - 熵反映跨域程度
        """
        if not concepts:
            return self._fallback_estimate(paper)

        levels = [c.level for c in concepts]
        scores = [c.score for c in concepts]

        # 1. 最低层级：技术的下限在哪里
        min_level = min(levels)
        # 2. 最高层级：技术的上限在哪里
        max_level = max(levels)
        # 3. 加权均值（用于辅助判断）
        total_weight = sum(scores)
        if total_weight > 0:
            mean_level = sum(l * s for l, s in zip(levels, scores)) / total_weight
        else:
            mean_level = sum(levels) / len(levels)

        # 4. 高层级概念（level >= 3）的权重占比
        high_level_weight = sum(s for l, s in zip(levels, scores) if l >= 3) / max(total_weight, 0.001)

        # 5. 概念分布的香农熵
        from collections import Counter
        level_counts = Counter(levels)
        total = len(concepts)
        entropy = 0.0
        for count in level_counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        max_entropy = math.log2(len(level_counts)) if len(level_counts) > 1 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        # 6. 合成分数
        # 排除 level=0 后，几乎每篇 AI 论文都有 level=1 的 Artificial Intelligence。
        # 真正的区分信号在 level 2-3 概念的占比。
        # level 3 概念（Object Detection, Transformer 等）越多 → 越应用导向 → 越低分
        
        # 过滤掉 level=0 的概念
        filtered_levels = [l for l in levels if l > 0]
        
        # 计算非 level-0 概念中 level>=3 的权重占比
        non_zero_scores = [s for l, s in zip(levels, scores) if l > 0]
        non_zero_total = sum(non_zero_scores) if non_zero_scores else 1.0
        # high_ratio 已经算了，但需要确认是相对所有还是非0
        actual_high_ratio = sum(s for l, s in zip(levels, scores) if l >= 3) / max(non_zero_total, 0.001)
        
        # 计算 level=2 的权重（中等抽象层级）
        level2_weight = sum(s for l, s in zip(levels, scores) if l == 2) / max(non_zero_total, 0.001)

        # 基础分：有 level=1 概念说明涉及基础问题 → 4.0 起步
        # 只有 level>=2 概念 → 3.0 起步
        has_level1 = 1 in filtered_levels
        base_score = 4.0 if has_level1 else 3.0

        # level=3 惩罚：高比例 level-3 概念 → 应用导向 → 扣分
        l3_penalty = actual_high_ratio * 2.5
        
        # level=2 中性：中等抽象，轻微加分
        l2_bonus = level2_weight * 0.5
        
        # 熵奖励：概念分散说明跨域
        entropy_bonus = normalized_entropy * 0.5

        raw_score = base_score - l3_penalty + l2_bonus + entropy_bonus
        score = self.clamp(raw_score)

        # 置信度
        confidence = min(1.0, len(concepts) / 8.0)

        evidence = {
            "level3_ratio": round(actual_high_ratio, 3),
            "level2_ratio": round(level2_weight, 3),
            "num_concepts": len(concepts),
            "entropy": round(entropy, 3),
            "level_distribution": dict(level_counts),
        }

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _fallback_estimate(self, paper: dict) -> dict:
        """无概念数据时的降级估算。

        通过标题/摘要中是否包含特定关键词来粗略判断问题层级。
        """
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        text = title + " " + abstract

        # 底层问题关键词（对应高抽象层级）
        high_level_keywords = [
            "training", "optimization", "learning algorithm", "gradient",
            "representation", "attention mechanism", "architecture",
            "backbone", "pretraining", "foundation model",
        ]
        # 上层问题关键词（对应低抽象层级）
        low_level_keywords = [
            "detection", "segmentation", "classification on",
            "benchmark for", "dataset for", "application of",
        ]

        high_count = sum(1 for kw in high_level_keywords if kw in text)
        low_count = sum(1 for kw in low_level_keywords if kw in text)

        if high_count > low_count:
            score = self.clamp(3.0 + (high_count - low_count) * 0.5)
        elif low_count > high_count:
            score = self.clamp(3.0 - (low_count - high_count) * 0.5)
        else:
            score = 2.5

        return {
            "score": round(score, 2),
            "confidence": 0.35,
            "evidence": {
                "method": "keyword_fallback",
                "high_level_matches": high_count,
                "low_level_matches": low_count,
            },
        }
