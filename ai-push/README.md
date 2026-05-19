# AI Push — AI 前沿信息自动化推送

每日自动采集海外 AI 前沿资讯（HackerNews、Reddit、arXiv），经 DeepSeek LLM 摘要翻译后，通过 Server酱推送到微信。

## 核心能力

- **多源采集** — HackerNews 热帖、Reddit r/MachineLearning、arXiv 最新论文
- **LLM 智能摘要** — DeepSeek 模型自动翻译为中文并提炼要点
- **兴趣过滤** — 关键词匹配，只推送关注的领域
- **微信直达** — Server酱推送到微信公众号，无需打开任何 App
- **定时全自动** — cron 每天 UTC 0:20（北京时间 8:20）执行

## 扩展模块

- `stock_briefing.py` — A股盘前简报，Tushare 数据 + LLM 解读
- `wechat_bot.py` — 微信公众号消息接口（交互机器人）

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY 和 SERVERCHAN_SENDKEY

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行推送
python ai_push.py

# 4. 配置 cron 定时任务
# 每天早 8:20 执行
# 20 8 * * * cd /path/to/ai-push && python ai_push.py
```

## 部署

已在 DigitalOcean VPS 上通过 cron 稳定运行，详见 `VPS/` 目录下的部署文档。

## 技术栈

Python · DeepSeek API · Server酱 · HackerNews API · Reddit API · arXiv API · cron
