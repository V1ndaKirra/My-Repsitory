"""
中国法律知识库 MCP Server (HTTP/SSE 模式)
供远程 AI 客户端（Claude Desktop、Hanako 等）通过 HTTP 调用
"""
import json, os, sys, asyncio
import chromadb
import requests
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
import uvicorn

# ============================================================
# 配置
# ============================================================
DB_PATH = os.environ.get('LAW_DB_PATH', '/home/hanako/law_db')
SILICONFLOW_API_KEY = os.environ['SILICONFLOW_API_KEY']
SILICONFLOW_BASE_URL = 'https://api.siliconflow.cn/v1'
EMBEDDING_MODEL = 'BAAI/bge-large-zh-v1.5'
SERVER_PORT = int(os.environ.get('MCP_PORT', '8765'))

# 初始化 ChromaDB
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_collection('chinese_laws')
print(f"[MCP] 知识库已加载: {collection.count()} 条法律条文")

# ============================================================
# 工具函数
# ============================================================
def embed_query(query: str) -> list:
    resp = requests.post(
        f"{SILICONFLOW_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": [query]},
        timeout=30
    )
    if resp.status_code != 200:
        raise Exception(f"Embedding error: {resp.status_code}")
    return resp.json()['data'][0]['embedding']

def search_law(query: str, top_k: int = 5) -> list:
    query_embedding = embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    output = []
    for i in range(len(results['documents'][0])):
        meta = results['metadatas'][0][i]
        doc = results['documents'][0][i]
        dist = results['distances'][0][i]
        output.append({
            "rank": i + 1,
            "score": round(1 - dist, 4),
            "law": meta.get('law', ''),
            "article_number": meta['article_number'],
            "content": doc,
            "reference": f"《{meta.get('law', '')}》第{meta['article_number']}条"
        })
    return output

def get_article(law_name: str, article_number: int) -> dict:
    results = collection.get(
        where={"$and": [{"law": law_name}, {"article_number": article_number}]},
        include=["documents", "metadatas"]
    )
    if results['documents']:
        return {"found": True, "content": results['documents'][0], "metadata": results['metadatas'][0]}
    return {"found": False}

# ============================================================
# MCP Server
# ============================================================
mcp_server = Server("chinese-law-mcp")

@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_law",
            description="搜索中国法律法规。输入自然语言问题，返回最相关的法律条文原文及出处。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "法律问题，如：业主未入住是否需要缴纳物业费"},
                    "top_k": {"type": "integer", "description": "返回结果数量，默认5", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_article",
            description="获取指定法律的特定条文原文。",
            inputSchema={
                "type": "object",
                "properties": {
                    "law_name": {"type": "string", "description": "法律名称，如：中华人民共和国民法典"},
                    "article_number": {"type": "integer", "description": "条文编号，如：944"}
                },
                "required": ["law_name", "article_number"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_law":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        results = search_law(query, top_k)
        text = f"【法律检索结果】查询：{query}\n知识库共 {collection.count()} 条法律条文\n\n"
        for r in results:
            text += f"{'='*50}\n"
            text += f"#{r['rank']} {r['reference']}（相关性：{r['score']}）\n"
            text += f"{r['content']}\n\n"
        return [TextContent(type="text", text=text)]
    
    elif name == "get_article":
        law_name = arguments.get("law_name", "")
        article_number = arguments.get("article_number", 0)
        result = get_article(law_name, article_number)
        if result['found']:
            text = f"《{law_name}》第{article_number}条\n{result['content']}"
        else:
            text = f"未找到《{law_name}》第{article_number}条。\n当前知识库包含：民法典(1260条)、刑法(451条)"
        return [TextContent(type="text", text=text)]
    
    return [TextContent(type="text", text=f"未知工具：{name}")]

# ============================================================
# HTTP/SSE 传输层
# ============================================================
sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(streams[0], streams[1], 
            InitializationCapabilities(sampling=None, experimental=None, roots=None),
            NotificationOptions())

async def health(request):
    return JSONResponse({
        "status": "ok",
        "service": "chinese-law-mcp",
        "articles": collection.count(),
        "laws": ["中华人民共和国民法典(1260条)", "中华人民共和国刑法(451条)"]
    })

app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Route("/health", endpoint=health),
])

if __name__ == '__main__':
    print(f"[MCP] 启动 HTTP/SSE 服务器，端口 {SERVER_PORT}")
    print(f"[MCP] 健康检查: http://localhost:{SERVER_PORT}/health")
    print(f"[MCP] MCP 端点: http://localhost:{SERVER_PORT}/sse")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
