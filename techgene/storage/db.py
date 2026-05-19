"""数据库连接与 CRUD 操作

SQLite 单文件，零配置。Session 是短生命周期的，
每次操作用完即关，不跨请求持有。
"""

import os
from contextlib import contextmanager
from datetime import datetime
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import Base, Paper, DimensionScore, RawSignal, Alert

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/techgene.db")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{DATABASE_PATH}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def init_db():
    """创建所有表（幂等）。"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info(f"数据库初始化完成: {DATABASE_PATH}")


@contextmanager
def get_session():
    """获取数据库会话的上下文管理器。
    
    expire_on_commit=False 确保 session 关闭后对象属性仍可访问。
    """
    session = Session(get_engine(), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Paper CRUD ──


def upsert_paper(paper_data: dict) -> Paper:
    """插入或更新论文。返回 Paper 对象。"""
    with get_session() as sess:
        paper = sess.get(Paper, paper_data["arxiv_id"])
        if paper is None:
            paper = Paper(id=paper_data["arxiv_id"])
            sess.add(paper)

        paper.title = paper_data.get("title", "")
        paper.set_authors(paper_data.get("authors", []))
        paper.abstract = paper_data.get("abstract", "")
        paper.source = paper_data.get("source", "arxiv")
        paper.set_categories(paper_data.get("categories", []))
        paper.pdf_url = paper_data.get("pdf_url", "")
        paper.last_updated_at = datetime.utcnow()

        if paper_data.get("published"):
            try:
                paper.published_date = datetime.fromisoformat(
                    paper_data["published"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        sess.flush()
        return paper


def get_paper(paper_id: str) -> Paper | None:
    """获取单篇论文。"""
    with get_session() as sess:
        return sess.get(Paper, paper_id)


def get_papers_without_scores(limit: int = 100) -> list[Paper]:
    """获取尚未评分的论文。"""
    with get_session() as sess:
        return (
            sess.query(Paper)
            .outerjoin(DimensionScore)
            .filter(DimensionScore.id.is_(None))
            .limit(limit)
            .all()
        )


def get_papers_needing_update(dimension: str, since_hours: int = 24) -> list[Paper]:
    """获取指定维度超过 since_hours 未更新的论文（用于延迟维度更新）。"""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(hours=since_hours)
    with get_session() as sess:
        # 获取该维度评分最旧的论文
        subq = (
            sess.query(
                DimensionScore.paper_id,
                DimensionScore.evaluated_at.label("last_eval"),
            )
            .filter(DimensionScore.dimension == dimension)
            .subquery()
        )

        return (
            sess.query(Paper)
            .outerjoin(subq, Paper.id == subq.c.paper_id)
            .filter(
                (subq.c.last_eval.is_(None))  # 从未评分
                | (subq.c.last_eval < cutoff)  # 超过指定时间
            )
            .limit(50)
            .all()
        )


# ── Dimension Score CRUD ──


def save_dimension_score(
    paper_id: str,
    dimension: str,
    score: float,
    confidence: float = 0.5,
    evidence: dict | None = None,
):
    """保存维度评分（每次评估追加一条新记录，保留历史）。"""
    with get_session() as sess:
        ds = DimensionScore(
            paper_id=paper_id,
            dimension=dimension,
            score=score,
            confidence=confidence,
        )
        if evidence:
            ds.set_evidence(evidence)
        sess.add(ds)


def get_latest_scores(paper_id: str) -> dict[str, float]:
    """获取论文最新的各维度评分。"""
    with get_session() as sess:
        # SQLite 子查询取每个维度的最新记录
        from sqlalchemy import func

        subq = (
            sess.query(
                DimensionScore.dimension,
                func.max(DimensionScore.evaluated_at).label("max_date"),
            )
            .filter(DimensionScore.paper_id == paper_id)
            .group_by(DimensionScore.dimension)
            .subquery()
        )

        results = (
            sess.query(DimensionScore)
            .join(
                subq,
                (DimensionScore.dimension == subq.c.dimension)
                & (DimensionScore.evaluated_at == subq.c.max_date)
                & (DimensionScore.paper_id == paper_id),
            )
            .all()
        )

        return {r.dimension: r.score for r in results}


# ── Raw Signal CRUD ──


def save_raw_signal(paper_id: str, signal_type: str, value: float, source: str):
    """保存原始信号快照。"""
    with get_session() as sess:
        signal = RawSignal(
            paper_id=paper_id,
            signal_type=signal_type,
            value=value,
            source=source,
        )
        sess.add(signal)


# ── Alert CRUD ──


def save_alert(paper_id: str, alert_type: str, message: str, severity: str = "info"):
    """保存告警。返回 Alert 对象。"""
    with get_session() as sess:
        alert = Alert(
            paper_id=paper_id,
            alert_type=alert_type,
            message=message,
            severity=severity,
        )
        sess.add(alert)
        sess.flush()
        sess.expunge(alert)
        return alert


def get_unacknowledged_alerts(limit: int = 10) -> list[Alert]:
    """获取未确认的告警。"""
    with get_session() as sess:
        return (
            sess.query(Alert)
            .filter(Alert.acknowledged == False)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .all()
        )
