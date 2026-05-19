"""
AI 前沿推送 — 主脚本
采集 → 去重 → LLM摘要 → 企微推送 → SQLite存档
运行: python ai_push.py
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import requests
import feedparser

# ============================================================
# 配置
# ============================================================

CONFIG = {
    # 推送通道（可多开，enabled 控制启用）
    "push_channels": {
        "serverchan": {
            "enabled": True,
            "sendkey": os.environ.get("SERVERCHAN_SENDKEY", ""),
        },
        "wecom": {
            "enabled": False,
            "webhook": os.environ.get("WECOM_WEBHOOK", ""),
        },
    },

    # DeepSeek API
    "deepseek_api_key": os.environ["DEEPSEEK_API_KEY"],
    "deepseek_base_url": "https://api.deepseek.com",

    # SQLite 数据库
    "db_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_push.db"),

    # 每日推送最大条数
    "max_items": 10,

    # 兴趣标签关键词
    "interest_keywords": {
        "金融": ["finance", "trading", "stock", "market", "quantitative", "fintech", "量化", "金融", "股票", "交易"],
        "编程": ["code", "programming", "developer", "agent", "copilot", "tool", "coding", "编程", "代码", "工具"],
        "产品": ["launch", "product", "startup", "pricing", "release", "发布", "产品", "上线"],
    },

    # 请求头（避免被拦截）
    "headers": {
        "User-Agent": "Mozilla/5.0 (compatible; ai-push-bot/1.0; +https://github.com/hanako/ai-push)"
    },
}

# ============================================================
# 日志
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("ai-push")

# ============================================================
# 数据库
# ============================================================

def init_db():
    conn = sqlite3.connect(CONFIG["db_path"])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            summary_zh TEXT,
            source TEXT NOT NULL,
            source_type TEXT DEFAULT 'other',
            tags TEXT DEFAULT '',
            fetched_at TEXT NOT NULL,
            pushed INTEGER DEFAULT 0,
            UNIQUE(url)
        )
    """)
    conn.commit()
    return conn


def save_item(conn, item: dict):
    """保存一条信息，URL 去重"""
    try:
        conn.execute("""
            INSERT OR IGNORE INTO items (title, url, summary_zh, source, source_type, tags, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["title"],
            item["url"],
            item.get("summary_zh", ""),
            item["source"],
            item.get("source_type", "other"),
            ",".join(item.get("tags", [])),
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
        return True
    except Exception as e:
        log.warning(f"保存失败: {e}")
        return False


def is_duplicate(conn, url: str) -> bool:
    cur = conn.execute("SELECT COUNT(*) FROM items WHERE url = ?", (url,))
    return cur.fetchone()[0] > 0

# ============================================================
# 信息源采集
# ============================================================

def fetch_arxiv(categories=None, max_results=10):
    """采集 ArXiv 最新论文"""
    if categories is None:
        categories = ["cs.AI", "cs.CL", "cs.LG"]
    
    items = []
    for cat in categories:
        try:
            url = f"https://export.arxiv.org/api/query?search_query=cat:{cat}&sortBy=submittedDate&sortOrder=descending&start=0&max_results={max_results}"
            resp = requests.get(url, headers=CONFIG["headers"], timeout=20)
            feed = feedparser.parse(resp.content)
            
            for entry in feed.entries[:max_results]:
                arxiv_id = entry.id.split("/")[-1]
                items.append({
                    "title": entry.title.strip().replace("\n", " "),
                    "url": entry.link,
                    "summary_en": entry.summary[:300] if hasattr(entry, "summary") else "",
                    "source": f"arXiv:{cat}",
                    "source_type": "paper",
                    "date": entry.published if hasattr(entry, "published") else "",
                })
            log.info(f"  arXiv {cat}: {len(feed.entries[:max_results])} 篇")
        except Exception as e:
            log.warning(f"  arXiv {cat} 失败: {e}")
    
    return items


def fetch_hf_daily_papers():
    """采集 HuggingFace Daily Papers"""
    items = []
    try:
        resp = requests.get("https://huggingface.co/api/daily_papers", 
                          headers=CONFIG["headers"], timeout=15)
        papers = resp.json()
        for p in papers[:10]:
            items.append({
                "title": p.get("title", "").strip(),
                "url": f"https://huggingface.co/papers/{p.get('paper', {}).get('id', '')}",
                "summary_en": "",
                "source": "HuggingFace",
                "source_type": "paper",
                "date": p.get("publishedAt", ""),
            })
        log.info(f"  HuggingFace: {len(papers[:10])} 篇")
    except Exception as e:
        log.warning(f"  HuggingFace 失败: {e}")
    return items


def fetch_github_trending():
    """采集 GitHub AI/ML 热门仓库"""
    items = []
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://api.github.com/search/repositories?q=ai+machine+learning+llm+created:>={today}&sort=stars&order=desc&per_page=5"
        resp = requests.get(url, headers=CONFIG["headers"], timeout=15)
        data = resp.json()
        
        for repo in data.get("items", [])[:5]:
            items.append({
                "title": f"{repo['full_name']} - {repo.get('description', '')[:100]}",
                "url": repo["html_url"],
                "summary_en": repo.get("description", ""),
                "source": "GitHub",
                "source_type": "repo",
                "date": repo.get("created_at", ""),
            })
        log.info(f"  GitHub: {len(data.get('items', [])[:5])} 个仓库")
    except Exception as e:
        log.warning(f"  GitHub 失败: {e}")
    return items


def fetch_producthunt():
    """采集 ProductHunt AI 新品"""
    items = []
    try:
        resp = requests.get("https://www.producthunt.com/feed", 
                          headers=CONFIG["headers"], timeout=15)
        feed = feedparser.parse(resp.content)
        
        for entry in feed.entries[:10]:
            title = entry.title or ""
            # 简单过滤 AI 相关
            ai_keywords = ["ai", "gpt", "llm", "claude", "copilot", "agent", "chat", "model", "generative"]
            if not any(kw in title.lower() for kw in ai_keywords):
                continue
            items.append({
                "title": title.strip(),
                "url": entry.link,
                "summary_en": entry.get("summary", "")[:150] if hasattr(entry, "summary") else "",
                "source": "ProductHunt",
                "source_type": "product",
                "date": entry.published if hasattr(entry, "published") else "",
            })
        log.info(f"  ProductHunt: {len(items)} 个 AI 产品")
    except Exception as e:
        log.warning(f"  ProductHunt 失败: {e}")
    return items


def fetch_openai_blog():
    """采集 OpenAI 官方博客"""
    items = []
    try:
        resp = requests.get("https://openai.com/news/rss.xml", 
                          headers=CONFIG["headers"], timeout=15)
        feed = feedparser.parse(resp.content)
        
        for entry in feed.entries[:5]:
            items.append({
                "title": entry.title.strip(),
                "url": entry.link,
                "summary_en": entry.get("summary", "")[:200] if hasattr(entry, "summary") else "",
                "source": "OpenAI",
                "source_type": "news",
                "date": entry.published if hasattr(entry, "published") else "",
            })
        log.info(f"  OpenAI: {len(feed.entries[:5])} 篇")
    except Exception as e:
        log.warning(f"  OpenAI 失败: {e}")
    return items


def fetch_google_ai_blog():
    """采集 Google AI 博客"""
    items = []
    try:
        resp = requests.get("https://blog.google/technology/ai/rss/", 
                          headers=CONFIG["headers"], timeout=15)
        feed = feedparser.parse(resp.content)
        
        for entry in feed.entries[:5]:
            items.append({
                "title": entry.title.strip(),
                "url": entry.link,
                "summary_en": entry.get("summary", "")[:200] if hasattr(entry, "summary") else "",
                "source": "Google AI",
                "source_type": "news",
                "date": entry.published if hasattr(entry, "published") else "",
            })
        log.info(f"  Google AI: {len(feed.entries[:5])} 篇")
    except Exception as e:
        log.warning(f"  Google AI 失败: {e}")
    return items


def fetch_anthropic_research():
    """采集 Anthropic Research 页面（HTML 抓取）"""
    items = []
    try:
        resp = requests.get("https://www.anthropic.com/research", 
                          headers=CONFIG["headers"], timeout=15)
        text = resp.text
        
        # 简单正则提取文章标题和链接
        import re
        # 匹配文章卡片：标题在 h 标签内，链接格式为 /research/xxx
        pattern = r'<a[^>]*href="(/research/[^"]+)"[^>]*>.*?<h[2-4][^>]*>(.*?)</h[2-4]>'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for href, title in matches[:5]:
            title = re.sub(r'<[^>]+>', '', title).strip()
            items.append({
                "title": title,
                "url": f"https://www.anthropic.com{href}",
                "summary_en": "",
                "source": "Anthropic",
                "source_type": "research",
                "date": "",
            })
        log.info(f"  Anthropic: {len(items)} 篇")
    except Exception as e:
        log.warning(f"  Anthropic 失败: {e}")
    return items

# ============================================================
# LLM 摘要
# ============================================================

def call_deepseek(prompt: str, max_tokens: int = 200) -> str:
    """调用 DeepSeek API"""
    api_key = CONFIG["deepseek_api_key"]
    if not api_key:
        log.warning("未设置 DEEPSEEK_API_KEY，跳过 LLM 摘要")
        return ""
    
    try:
        resp = requests.post(
            f"{CONFIG['deepseek_base_url']}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=30,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"DeepSeek 调用失败: {e}")
        return ""


def summarize_item(item: dict) -> str:
    """为一篇信息生成一句话中文摘要"""
    title = item["title"]
    summary_en = item.get("summary_en", "")

    prompt = f"""请用一句简洁的中文（不超过40个字）概括以下AI相关内容的要点：

标题：{title}
原文摘要：{summary_en[:200]}

要求：
- 一句话，不超过40个汉字
- 突出最核心的观点或发现
- 不要「本文」「这项研究」等套话
- 直接陈述内容本身"""

    return call_deepseek(prompt, max_tokens=80)


def match_interest_tags(item: dict) -> list:
    """匹配兴趣标签"""
    text = (item["title"] + " " + item.get("summary_en", "")).lower()
    tags = []
    for tag, keywords in CONFIG["interest_keywords"].items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def deduplicate(items: list, conn) -> list:
    """去重：排除已存档的 URL + 按标题相似度过滤"""
    seen_urls = set()
    unique = []
    
    for item in items:
        url = item["url"]
        if url in seen_urls:
            continue
        if is_duplicate(conn, url):
            continue
        seen_urls.add(url)
        unique.append(item)
    
    return unique

# ============================================================
# 企微推送
# ============================================================

def format_push_content(items: list, date_str: str) -> str:
    """格式化推送内容"""
    lines = [
        f"## 🤖 AI 前沿速递 {date_str}",
        "",
    ]
    
    for item in items[:CONFIG["max_items"]]:
        tags_str = " ".join([f"`{t}`" for t in item.get("tags", [])])
        summary = item.get("summary_zh", item["title"][:60])
        src = item["source"]
        url = item["url"]
        # 国内被墙的源标注 🔒
        blocked_sources = ["HuggingFace", "OpenAI", "Google AI"]
        lock = "🔒" if any(b in src for b in blocked_sources) else ""
        line = f"- [{summary}]({url}){lock} *{src}*"
        if tags_str:
            line += f" {tags_str}"
        lines.append(line)
    
    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M')} | 共 {min(len(items), CONFIG['max_items'])} 条")
    lines.append("🔒 = 需VPN访问")
    
    return "\n".join(lines)


def push_to_serverchan(title: str, content: str) -> bool:
    """推送到 Server酱（微信公众号）"""
    import subprocess
    cfg = CONFIG["push_channels"]["serverchan"]
    try:
        url = f"https://sctapi.ftqq.com/{cfg['sendkey']}.send"
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", url,
             "--data-urlencode", f"title={title}",
             "--data-urlencode", f"desp={content}",
             "--connect-timeout", "10", "--max-time", "90"],
            capture_output=True, text=True, timeout=100
        )
        data = json.loads(result.stdout)
        if data.get("code") == 0:
            log.info("Server酱推送成功")
            return True
        else:
            log.warning(f"Server酱推送失败: {data}")
            return False
    except Exception as e:
        log.error(f"Server酱推送异常: {e}")
        return False


def push_to_wecom(markdown_content: str) -> bool:
    """推送到企业微信"""
    try:
        cfg = CONFIG["push_channels"]["wecom"]
        resp = requests.post(
            cfg["webhook"],
            json={
                "msgtype": "markdown",
                "markdown": {"content": markdown_content}
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") == 0:
            log.info("企微推送成功")
            return True
        else:
            log.warning(f"企微推送失败: {data}")
            return False
    except Exception as e:
        log.error(f"企微推送异常: {e}")
        return False

# ============================================================
# 主流程
# ============================================================

def main():
    log.info("=" * 40)
    log.info("AI 前沿推送开始")
    
    # 初始化数据库
    conn = init_db()
    
    # 1. 采集所有信息源
    log.info("[1/4] 采集信息源...")
    all_items = []
    # TechGene 已接管论文追踪，AI 推送仅关注产品动态
    # all_items.extend(fetch_arxiv())
    # all_items.extend(fetch_hf_daily_papers())
    all_items.extend(fetch_producthunt())
    all_items.extend(fetch_openai_blog())
    all_items.extend(fetch_google_ai_blog())
    all_items.extend(fetch_anthropic_research())
    all_items.extend(fetch_github_trending())
    
    log.info(f"  共采集 {len(all_items)} 条原始信息")
    
    # 2. 去重
    log.info("[2/4] 去重...")
    items = deduplicate(all_items, conn)
    log.info(f"  去重后剩余 {len(items)} 条")
    
    # 3. LLM 摘要 + 兴趣标签
    has_llm = bool(CONFIG.get("deepseek_api_key") or os.environ.get("DEEPSEEK_API_KEY"))
    if has_llm:
        log.info("[3/4] LLM 摘要 + 标签匹配...")
        for item in items:
            if any('\u4e00' <= c <= '\u9fff' for c in item["title"]):
                item["summary_zh"] = item["title"][:60]
            else:
                zh = summarize_item(item)
                item["summary_zh"] = zh
            item["tags"] = match_interest_tags(item)
            time.sleep(0.5)
    else:
        log.info("[3/4] 无 LLM API Key，跳过摘要（用原标题）")
    
    # 4. 精选 + 推送
    log.info("[4/4] 推送...")
    # 优先级排序：有摘要的 > 有标签的 > 其他
    items.sort(key=lambda x: (
        len(x.get("tags", [])),
        len(x.get("summary_zh", "")),
    ), reverse=True)
    
    push_items = items[:CONFIG["max_items"]]
    
    # 保存到数据库
    for item in push_items:
        save_item(conn, item)
    
    # 格式化并推送
    today = datetime.now().strftime("%m/%d")
    content = format_push_content(push_items, today)
    
    if CONFIG.get("dry_run"):
        log.info("DRY RUN — 不实际推送")
        print(content)
    else:
        sc = CONFIG["push_channels"].get("serverchan", {})
        if sc.get("enabled"):
            push_to_serverchan(f"AI 前沿速递 {today}", content)
        wc = CONFIG["push_channels"].get("wecom", {})
        if wc.get("enabled"):
            push_to_wecom(content)
    
    conn.close()
    log.info(f"完成！推送 {len(push_items)} 条")


if __name__ == "__main__":
    main()
