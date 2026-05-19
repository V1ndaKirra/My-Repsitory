"""告警引擎 + Server酱推送

告警规则：
- new_high_potential: 新论文综合评分 >= 3.5，通知用户关注
- score_surge: 某个维度分跳升 >= 2.0 分
- cross_domain: 抽象层级 >= 4.0 且有跨域扩散信号
- velocity_alarm: GitHub star 日增异常
"""

import os
import httpx
from datetime import datetime, timedelta
from loguru import logger

from storage.db import (
    get_session,
    save_alert,
    get_unacknowledged_alerts,
    get_latest_scores,
)
from storage.models import Paper, DimensionScore, Alert

SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")

# 告警推送上限（每天最多推几条）
MAX_DAILY_PUSHES = 5


def check_alerts(dry_run: bool = False) -> list[dict]:
    """扫描数据库，匹配告警规则，返回触发的告警列表。

    每条告警: {paper_id, alert_type, severity, message}
    """
    alerts = []

    alerts.extend(_check_new_high_potential())
    alerts.extend(_check_score_surge())
    alerts.extend(_check_cross_domain())

    # 去重：同一 paper_id + alert_type 今天已触发过的跳过
    recent = _get_recent_alert_ids(hours=24)
    alerts = [a for a in alerts if f"{a['paper_id']}:{a['alert_type']}" not in recent]

    if not dry_run:
        for alert_data in alerts:
            save_alert(
                paper_id=alert_data["paper_id"],
                alert_type=alert_data["alert_type"],
                message=alert_data["message"],
                severity=alert_data["severity"],
            )

    return alerts


def push_alerts(alerts: list[dict], dry_run: bool = False) -> int:
    """推送告警到 Server酱。返回成功推送数。"""
    if not alerts:
        return 0

    # 只推送 severity 最高的几条
    severity_order = {"critical": 3, "warning": 2, "info": 1}
    alerts_sorted = sorted(alerts, key=lambda a: severity_order.get(a["severity"], 0), reverse=True)
    to_push = alerts_sorted[:MAX_DAILY_PUSHES]

    pushed = 0
    for alert in to_push:
        msg = _format_alert_message(alert)
        if dry_run:
            logger.info(f"[DRY RUN] 推送: {msg[:80]}...")
            pushed += 1
        else:
            if _send_serverchan(alert["message"][:80], msg):
                pushed += 1

    return pushed


def _check_new_high_potential() -> list[dict]:
    """检查是否有新论文综合评分 >= 3.5。"""
    with get_session() as sess:
        recent = datetime.utcnow() - timedelta(days=30)
        papers = (
            sess.query(Paper)
            .filter(Paper.first_seen_at >= recent)
            .all()
        )

    alerts = []
    for paper in papers:
        scores = get_latest_scores(paper.id)
        if not scores:
            continue

        # 综合评分：已有维度的均值
        composite = sum(scores.values()) / len(scores)

        if composite >= 2.8:  # 七维综合阈值（7维比2维均值更低）
            dims_str = ", ".join(f"{k}={v:.1f}" for k, v in sorted(scores.items()))
            alerts.append(
                {
                    "paper_id": paper.id,
                    "alert_type": "new_high_potential",
                    "severity": "warning",
                    "message": (
                        f"🟡 新高分论文\n"
                        f"标题: {paper.title[:80]}\n"
                        f"综合: {composite:.1f}/5 | {dims_str}\n"
                        f"入库: {paper.first_seen_at.strftime('%m-%d %H:%M') if paper.first_seen_at else '?'}"
                    ),
                }
            )

    return alerts


def _check_score_surge() -> list[dict]:
    """检查是否有维度分突然跳升 >= 2.0。"""
    with get_session() as sess:
        # 查询最近两次评分，比较变化
        from sqlalchemy import func, and_

        # 获取每篇论文每个维度的最新两次评分
        subq = (
            sess.query(
                DimensionScore.paper_id,
                DimensionScore.dimension,
                DimensionScore.score,
                func.row_number()
                .over(
                    partition_by=(DimensionScore.paper_id, DimensionScore.dimension),
                    order_by=DimensionScore.evaluated_at.desc(),
                )
                .label("rn"),
            ).subquery()
        )

        latest_two = (
            sess.query(subq)
            .filter(subq.c.rn <= 2)
            .order_by(subq.c.paper_id, subq.c.dimension, subq.c.rn)
            .all()
        )

    # 按 paper_id + dimension 分组
    from collections import defaultdict

    pairs = defaultdict(list)
    for row in latest_two:
        pairs[(row.paper_id, row.dimension)].append(row.score)

    alerts = []
    for (paper_id, dim), scores_list in pairs.items():
        if len(scores_list) < 2:
            continue
        delta = scores_list[0] - scores_list[1]
        if delta >= 2.0:
            alerts.append(
                {
                    "paper_id": paper_id,
                    "alert_type": f"score_surge_{dim}",
                    "severity": "warning",
                    "message": (
                        f"📈 维度跳升\n"
                        f"维度: {dim}\n"
                        f"变化: {scores_list[1]:.1f} → {scores_list[0]:.1f} (+{delta:.1f})\n"
                        f"论文: {paper_id}"
                    ),
                }
            )

    return alerts


def _check_cross_domain() -> list[dict]:
    """检查抽象层级 >= 4.0 的论文（有跨域潜力）。"""
    alerts = []

    with get_session() as sess:
        papers = sess.query(Paper).all()

    for paper in papers:
        scores = get_latest_scores(paper.id)
        abst = scores.get("abstraction", 0)

        if abst >= 4.0:
            concepts = paper.get_concepts()
            # 检查概念是否跨领域
            if len(concepts) >= 4:
                alerts.append(
                    {
                        "paper_id": paper.id,
                        "alert_type": "cross_domain_potential",
                        "severity": "info",
                        "message": (
                            f"🔍 高抽象层级论文\n"
                            f"标题: {paper.title[:80]}\n"
                            f"抽象层级: {abst:.1f}/5 | 概念数: {len(concepts)}\n"
                            f"可能具有跨域扩散潜力"
                        ),
                    }
                )

    return alerts


def _get_recent_alert_ids(hours: int = 24) -> set:
    """获取最近 N 小时内已触发的告警 (paper_id:alert_type)。"""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    with get_session() as sess:
        recent = (
            sess.query(Alert)
            .filter(Alert.created_at >= cutoff)
            .all()
        )
        return {f"{a.paper_id}:{a.alert_type}" for a in recent}


def _format_alert_message(alert: dict) -> str:
    """格式化告警消息为推送文本。"""
    return alert["message"]


def _send_serverchan(title: str, content: str) -> bool:
    """通过 Server酱发送推送。"""
    if not SENDKEY:
        logger.warning("Server酱 sendkey 未配置")
        return False

    url = f"https://sctapi.ftqq.com/{SENDKEY}.send"

    try:
        resp = httpx.post(
            url,
            data={"title": title, "desp": content},
            timeout=10.0,
        )
        data = resp.json()
        if data.get("code") == 0:
            logger.info(f"Server酱推送成功: {title}")
            return True
        else:
            logger.warning(f"Server酱推送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"Server酱推送异常: {e}")
        return False
