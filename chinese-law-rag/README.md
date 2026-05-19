# Chinese Law RAG — 中文法律检索增强生成

基于 ChromaDB + BGE Embedding 的中文法律知识库，支持语义检索与条文精准定位，通过 MCP (Model Context Protocol) 协议对外暴露检索服务。

## 核心能力

- **法律语料库** — 民法典（1260条）、刑法（451条）、劳动法、劳动合同法等核心法律
- **语义检索** — BGE-large-zh-v1.5 向量化，ChromaDB 存储，支持自然语言查询
- **MCP 服务** — FastMCP + SSE 协议，可被任意 MCP 客户端（Hanako、Claude Desktop 等）集成
- **多节点部署** — 支持本地 Windows + 远程 VPS 双节点，iptables 端口转发对外服务
- **版本审计** — 自动识别已废止法律（民法通、婚姻法等 9 部）与新版修订状态

## 项目结构

```
chinese-law-rag/
├── build_law_db.py          # 向量化入库脚本
├── download_laws.py         # 法律文本下载
├── parse_*.py               # HTML/TXT 解析脚本
├── extract_*.py             # 结构化提取脚本
├── mcp_server.py            # MCP Server (FastMCP + SSE)
├── mcp_server_http.py       # VPS 部署版本
├── mcp_server_local.py      # 本地 Windows 版本
├── *_articles.json          # 结构化法律条文
├── start_mcp.bat            # Windows 一键启动
└── LAW_STATUS.md            # 法律下载与版本状态
```

## 快速开始

```bash
# 1. 安装依赖
pip install chromadb fastmcp openai

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 SILICONFLOW_API_KEY

# 3. 构建向量库
python build_law_db.py

# 4. 启动 MCP 服务
python mcp_server.py
# 或 Windows: 双击 start_mcp.bat
```

## MCP 工具

| 工具 | 功能 |
|---|---|
| `search_law` | 语义检索法律条文 |
| `get_article` | 精确获取指定条文 |

## 部署

- **本地**: `localhost:8765`
- **VPS**: `139.59.117.164:443`（iptables 转发至 8765）
- **进程管理**: systemd user service（VPS）

## 技术栈

Python · ChromaDB · BGE Embedding · FastMCP · SiliconFlow API · systemd
