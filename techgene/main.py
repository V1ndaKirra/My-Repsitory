"""TechGene - 技术谱系追踪系统

用法:
    python main.py --once          # 单次采集 + 存储
    python main.py --dry-run       # 只采集不存储
    python main.py --daily         # 完整日常流程 (采集 + 评分 + 告警)
    python main.py --check-alerts  # 仅检查告警
"""

import argparse
import sys
from datetime import date, timedelta
from loguru import logger

from collectors.openalex import fetch_new_papers
from storage.db import (
    init_db,
    upsert_paper,
    get_paper,
    get_papers_without_scores,
    save_dimension_score,
    get_latest_scores,
)
from analyzers.abstraction import AbstractionAnalyzer
from analyzers.medium import MediumAnalyzer
from analyzers.interface import InterfaceAnalyzer
from analyzers.composability import ComposabilityAnalyzer
from analyzers.standardization import StandardizationAnalyzer
from analyzers.distance import DistanceAnalyzer
from analyzers.iteration import IterationAnalyzer
from notifier import check_alerts, push_alerts
from briefing import generate_briefing, generate_timeline

# 初始化所有分析器
ABSTRACTION = AbstractionAnalyzer()
MEDIUM = MediumAnalyzer()
INTERFACE = InterfaceAnalyzer()
COMPOSABILITY = ComposabilityAnalyzer()
STANDARDIZATION = StandardizationAnalyzer()
DISTANCE = DistanceAnalyzer()
ITERATION = IterationAnalyzer()

ANALYZERS = [
    ABSTRACTION,
    MEDIUM,
    INTERFACE,
    COMPOSABILITY,
    STANDARDIZATION,
    DISTANCE,
    ITERATION,
]


def setup_logging(level: str = "INFO"):
    """配置日志：控制台 + 文件（自动轮转 30 天）。"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:7}</level> | {message}",
    )
    logger.add(
        "logs/techgene_{time:YYYY-MM-DD}.log",
        level=level,
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:7} | {name}:{function}:{line} | {message}",
    )


def cmd_once(dry_run: bool = False):
    """单次采集存储：OpenAlex 发现新论文。"""
    logger.info("开始单次采集...")

    papers = fetch_new_papers(
        target_date=date.today() - timedelta(days=1),
        max_results=100,
    )

    if not papers:
        logger.warning("未获取到论文（可能是周末或节假日）")
        return

    if dry_run:
        logger.info(f"[DRY RUN] 采集到 {len(papers)} 篇，不写入数据库")
        for p in papers[:5]:
            logger.info(f"  - {p['title'][:80]}...")
        return

    init_db()
    saved = 0
    for p in papers:
        upsert_paper(p)
        saved += 1

    logger.info(f"入库完成: {saved} 篇")


def cmd_score():
    """对未评分论文运行所有分析器。"""
    init_db()
    unscored = get_papers_without_scores(limit=50)

    if not unscored:
        logger.info("所有论文已评分")
        return

    logger.info(f"待评分论文: {len(unscored)} 篇")

    for paper in unscored:
        # 构建分析器需要的 paper dict
        paper_data = {
            "arxiv_id": paper.id,
            "title": paper.title,
            "abstract": paper.abstract or "",
            "concepts": paper.get_concepts(),
            "citation_count": 0,
        }

        for analyzer in ANALYZERS:
            try:
                result = analyzer.analyze(paper_data)
                save_dimension_score(
                    paper_id=paper.id,
                    dimension=analyzer.dimension,
                    score=result["score"],
                    confidence=result["confidence"],
                    evidence=result["evidence"],
                )
            except Exception as e:
                logger.error(f"{analyzer.dimension} 评分失败 [{paper.id}]: {e}")

    logger.info("评分完成")


def cmd_daily():
    """完整日常流程。"""
    logger.info("=== TechGene 日常流程 ===")

    # Step 1: 采集新论文
    cmd_once(dry_run=False)

    # Step 2: 评分
    cmd_score()

    # Step 3: 告警检查 + 推送
    alerts = check_alerts(dry_run=False)
    if alerts:
        logger.info(f"触发 {len(alerts)} 条告警")
        pushed = push_alerts(alerts, dry_run=False)
        logger.info(f"推送 {pushed} 条告警")
    else:
        logger.info("无告警触发")

    # Step 4: 生成简报 + 时间线
    try:
        briefing = generate_briefing()
        with open("/var/www/techgene/daily_briefing.md", "w", encoding="utf-8") as f:
            f.write(briefing)
        logger.info(f"简报已生成: output/daily_briefing.md ({len(briefing)} 字)")

        timeline = generate_timeline()
        with open("/var/www/techgene/timeline.html", "w", encoding="utf-8") as f:
            f.write(timeline)
        logger.info(f"时间线已生成: output/timeline.html")
    except Exception as e:
        logger.error(f"简报/时间线生成失败: {e}")

    logger.info("=== 日常流程完成 ===")


def cmd_check_alerts():
    """检查告警规则并推送。"""
    logger.info("检查告警...")
    alerts = check_alerts(dry_run=True)
    if alerts:
        logger.info(f"发现 {len(alerts)} 条告警")
        for a in alerts:
            logger.info(f"  [{a['severity']}] {a['alert_type']}: {a['message'][:80]}")
        push_alerts(alerts, dry_run=False)
    else:
        logger.info("无告警触发")


def main():
    parser = argparse.ArgumentParser(description="TechGene 技术谱系追踪")
    parser.add_argument("--once", action="store_true", help="单次采集 + 存储")
    parser.add_argument("--dry-run", action="store_true", help="只采集不存储")
    parser.add_argument("--score", action="store_true", help="仅运行评分引擎")
    parser.add_argument("--daily", action="store_true", help="完整日常流程")
    parser.add_argument("--check-alerts", action="store_true", help="检查告警")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.once or args.dry_run:
        cmd_once(dry_run=args.dry_run)
    elif args.score:
        cmd_score()
    elif args.daily:
        cmd_daily()
    elif args.check_alerts:
        cmd_check_alerts()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
