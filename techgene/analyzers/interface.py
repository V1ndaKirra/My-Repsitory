"""维度二：接口通用性

衡量技术的输入/输出范式的通用程度。

Text ↔ Text  → 5 分（最通用，NLP 到一切文字任务）
Text → Image  → 4 分（文生图，覆盖面广但单向）
Image → Data  → 3 分（视觉理解，结构化输出）
特定 ↔ 特定  → 1-2 分（领域专用）

使用 DeepSeek LLM 分析论文摘要，判断 I/O 范式。
"""

from loguru import logger

from .base import BaseAnalyzer
from .llm_client import classify

# I/O 范式 → 分数映射
IO_SCORES = {
    "text_to_text": 5.0,
    "text_to_code": 4.5,
    "multimodal_to_text": 4.5,
    "text_to_image": 4.0,
    "text_to_video": 4.0,
    "image_to_text": 3.5,
    "image_to_data": 3.0,
    "data_to_data": 3.0,
    "image_to_image": 2.5,
    "specific_to_specific": 2.0,
}

IO_OPTIONS = list(IO_SCORES.keys())


class InterfaceAnalyzer(BaseAnalyzer):
    dimension = "interface"

    def analyze(self, paper: dict) -> dict:
        """分析论文的接口通用性。"""
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")

        if not abstract:
            # 无摘要时用标题估算
            text = title
            confidence = 0.3
        else:
            text = f"Title: {title}\nAbstract: {abstract}"
            confidence = 0.7

        # LLM 分类 I/O 范式
        io_type = classify(
            text,
            task="判断这项技术的输入输出范式是什么。例如：text_to_text 表示输入文本输出文本（如翻译、摘要），text_to_image 表示输入文本输出图像（如文生图），image_to_data 表示输入图像输出结构化数据（如目标检测）。",
            options=IO_OPTIONS,
        )

        score = self.clamp(IO_SCORES.get(io_type, 2.5))

        # 基于标题关键词做二次修正（有置信度的信号）
        score = self._keyword_adjustment(title.lower(), score)

        evidence = {
            "io_paradigm": io_type,
            "method": "llm_classification",
            "raw_score": IO_SCORES.get(io_type, 2.5),
        }

        logger.debug(f"接口通用性: {title[:40]} → {score:.1f} ({io_type})")

        return {"score": round(score, 2), "confidence": round(confidence, 2), "evidence": evidence}

    def _keyword_adjustment(self, title: str, score: float) -> float:
        """基于标题关键词微调分数。"""
        # 宽接口关键词
        broad_kw = ["universal", "general-purpose", "foundation", "multimodal", "any-to-any"]
        # 窄接口关键词
        narrow_kw = ["detection", "segmentation", "classification on", "for xyz dataset"]

        broad_hits = sum(1 for kw in broad_kw if kw in title)
        narrow_hits = sum(1 for kw in narrow_kw if kw in title)

        if broad_hits > narrow_hits:
            score += 0.3
        elif narrow_hits > broad_hits:
            score -= 0.3

        return self.clamp(score)
