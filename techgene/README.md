# TechGene — 技术谱系追踪系统

追踪深度学习关键技术的演进脉络，通过七维度框架量化评估每项技术的产业影响力，生成交互式时间线可视化与每日研究简报。

**在线 Demo**: [http://139.59.117.164:8080/timeline.html](http://139.59.117.164:8080/timeline.html)

## 核心能力

- **七维评分引擎** — 从抽象层级、接口通用性、可组合性、标准化效应、产业接口距离、扩散媒介、垂直迭代潜力七个维度评估技术影响力
- **自动化数据采集** — 对接 OpenAlex、arXiv、GitHub、Semantic Scholar API，抓取论文引用数与社区指标
- **交互式时间线** — ECharts 渲染，支持缩放拖拽、双轴联动、技术血缘关系线、七维 tooltip
- **每日简报** — Markdown 格式自动生成，Server酱推送到微信
- **定时全自动运行** — systemd timer 每天 UTC 7:00 执行

## 里程碑覆盖

| 技术 | 年份 | 综合评分亮点 |
|---|---|---|
| Backpropagation | 1986 | 接口通用性 5.0 |
| ImageNet | 2009 | 扩散媒介 4.5 |
| ResNet | 2015 | 可组合性 4.8 |
| YOLO | 2016 | 产业距离 1.0（极近） |
| AlphaGo | 2016 | 扩散媒介 5.0 |
| Transformer | 2017 | 接口 5.0 / 迭代 4.1 |
| Stable Diffusion | 2022 | 扩散媒介 4.8 |

## 项目结构

```
techgene/
├── analyzers/          # 七维度评分引擎
│   ├── abstraction.py
│   ├── interface.py
│   ├── composability.py
│   ├── standardization.py
│   ├── distance.py
│   ├── medium.py
│   ├── iteration.py
│   └── llm_client.py
├── collectors/         # 数据采集（OpenAlex, arXiv, GitHub）
├── storage/            # SQLAlchemy 数据模型
├── main.py             # 主流程入口
├── briefing.py         # 每日简报生成
├── notifier.py         # 微信推送
└── eval_phase3.py      # Phase 3 回溯评估
```

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行全流程
python main.py

# 4. 单独生成时间线
python main.py --timeline-only
```

## 技术栈

Python · SQLAlchemy · ECharts · OpenAlex API · DeepSeek API · Server酱 · systemd
