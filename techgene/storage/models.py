"""SQLAlchemy 数据模型

四张核心表:
- papers: 论文基本信息
- dimension_scores: 七维度评分时间序列
- raw_signals: 原始数据快照 (citations, stars, downloads)
- alerts: 告警记录
"""

import json
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True)  # arXiv ID
    title = Column(String, nullable=False)
    authors = Column(Text)  # JSON array
    abstract = Column(Text)
    published_date = Column(DateTime)
    source = Column(String, default="arxiv")
    categories = Column(Text)  # JSON array: arXiv categories
    pdf_url = Column(String)
    concepts = Column(Text)  # JSON: OpenAlex concepts
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow)

    scores = relationship("DimensionScore", back_populates="paper", cascade="all, delete-orphan")
    signals = relationship("RawSignal", back_populates="paper", cascade="all, delete-orphan")

    def set_authors(self, authors_list: list[str]):
        self.authors = json.dumps(authors_list, ensure_ascii=False)

    def get_authors(self) -> list[str]:
        return json.loads(self.authors) if self.authors else []

    def set_categories(self, cats: list[str]):
        self.categories = json.dumps(cats, ensure_ascii=False)

    def get_categories(self) -> list[str]:
        return json.loads(self.categories) if self.categories else []

    def set_concepts(self, concepts_list: list[dict]):
        self.concepts = json.dumps(concepts_list, ensure_ascii=False)

    def get_concepts(self) -> list[dict]:
        return json.loads(self.concepts) if self.concepts else []


class DimensionScore(Base):
    __tablename__ = "dimension_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
    dimension = Column(String, nullable=False)  # abstraction, interface, composability, ...
    score = Column(Float, nullable=False)  # 1.0 - 5.0
    confidence = Column(Float, default=0.5)  # 0.0 - 1.0
    evidence = Column(Text)  # JSON: 评分依据
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    paper = relationship("Paper", back_populates="scores")

    __table_args__ = (
        Index("idx_dim_scores_lookup", "paper_id", "dimension", "evaluated_at"),
    )

    def set_evidence(self, data: dict):
        self.evidence = json.dumps(data, ensure_ascii=False)

    def get_evidence(self) -> dict:
        return json.loads(self.evidence) if self.evidence else {}


class RawSignal(Base):
    __tablename__ = "raw_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
    signal_type = Column(String, nullable=False)  # citation_count, github_stars, hf_downloads
    value = Column(Float, nullable=False)
    source = Column(String)  # openalex, github, huggingface
    recorded_at = Column(DateTime, default=datetime.utcnow)

    paper = relationship("Paper", back_populates="signals")

    __table_args__ = (
        Index("idx_signals_lookup", "paper_id", "signal_type", "recorded_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
    alert_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String, default="info")  # info, warning, critical
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
