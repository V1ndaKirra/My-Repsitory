"""TechGene 分析器基类"""

from abc import ABC, abstractmethod


class BaseAnalyzer(ABC):
    """所有维度分析器的基类。"""

    # 维度名称，子类必须定义
    dimension: str = ""

    # 评分范围
    MIN_SCORE = 1.0
    MAX_SCORE = 5.0

    @abstractmethod
    def analyze(self, paper: dict) -> dict:
        """分析一篇论文，返回评分结果。

        Args:
            paper: 论文数据字典，包含 arxiv_id, title, abstract, concepts 等

        Returns:
            {
                "score": float,       # 1.0-5.0
                "confidence": float,  # 0.0-1.0
                "evidence": dict,     # 评分依据
            }
        """
        ...

    def clamp(self, score: float) -> float:
        """将分数限制在有效范围内。"""
        return max(self.MIN_SCORE, min(self.MAX_SCORE, score))
