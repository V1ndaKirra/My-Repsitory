"""
中国法律知识库 MCP Server
暴露 search_law 和 get_article 两个工具
支持 stdio 和 HTTP/SSE 两种传输模式
"""
import json, os, sys
import chromadb
import requests
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============================================================
# 配置
# ============================================================
DB_PATH = r'E:\Hanko-workspace\law_db'
SILICONFLOW_API_KEY = os.environ['SILICONFLOW_API_KEY']
SILICONFLOW_BASE_URL = 'https://api.siliconflow.cn/v1'
EMBEDDING_MODEL = 'BAAI/bge-large-zh-v1.5'

# 初始化 ChromaDB
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_collection('chinese_laws')

# ============================================================
# 工具函数
# ============================================================
def embed_query(query: str) -> list:
    """向量化查询文本"""
    resp = requests.post(
        f"{SILICONFLOW_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": [query]},
        timeout=30
    )
    if resp.status_code != 200:
        raise Exception(f"Embedding API error: {resp.status_code}")
    return resp.json()['data'][0]['embedding']

def search_law(query: str, top_k: int = 5) -> list:
    """检索相关法律条文"""
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
            "book": meta.get('book', ''),
            "chapter": meta.get('chapter', ''),
            "content": doc,
            "reference": f"《{meta.get('law', '')}》第{meta['article_number']}条"
        })
    return output

def get_article(law_name: str, article_number: int) -> dict:
    """获取指定法律的特定条文"""
    results = collection.get(
        where={"$and": [
            {"law": law_name},
            {"article_number": article_number}
        ]},
        include=["documents", "metadatas"]
    )
    if results['documents']:
        return {
            "found": True,
            "content": results['documents'][0],
            "metadata": results['metadatas'][0]
        }
    return {"found": False}

# ============================================================
# MCP Server
# ============================================================
server = Server("chinese-law-mcp")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_law",
            description="搜索中国法律法规。输入自然语言问题，返回最相关的法律条文原文。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "法律问题，用自然语言描述，例如：'业主未入住是否需要缴纳物业费'"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认5",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_article",
            description="获取指定法律的特定条文原文。需要提供法律名称和条文编号。",
            inputSchema={
                "type": "object",
                "properties": {
                    "law_name": {
                        "type": "string",
                        "description": "法律名称，例如：'中华人民共和国民法典'、'中华人民共和国刑法'"
                    },
                    "article_number": {
                        "type": "integer",
                        "description": "条文编号，例如：944"
                    }
                },
                "required": ["law_name", "article_number"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_law":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        results = search_law(query, top_k)
        
        text = f"查询：{query}\n\n"
        text += f"知识库共 {collection.count()} 条法律条文\n"
        text += "=" * 50 + "\n\n"
        
        for r in results:
            text += f"【{r['rank']}】{r['reference']}（相关性：{r['score']}）\n"
            text += f"所属编章：{r['book']} {r['chapter']}\n"
            text += f"条文内容：{r['content']}\n\n"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "get_article":
        law_name = arguments.get("law_name", "")
        article_number = arguments.get("article_number", 0)
        result = get_article(law_name, article_number)
        
        if result['found']:
            meta = result['metadata']
            text = f"《{law_name}》第{article_number}条\n"
            text += f"所属编章：{meta.get('book', '')} {meta.get('chapter', '')}\n"
            text += f"条文内容：{result['content']}"
        else:
            text = f"未找到《{law_name}》第{article_number}条"
        
        return [TextContent(type="text", text=text)]
    
    else:
        return [TextContent(type="text", text=f"未知工具：{name}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationCapabilities(
                sampling=None,
                experimental=None,
                roots=None
            ),
            NotificationOptions()
        )

if __name__ == '__main__':
    import asyncio
    print(f"MCP Server 启动中...")
    print(f"知识库: {collection.count()} 条法律条文")
    print(f"Embedding: {EMBEDDING_MODEL}")
    asyncio.run(main())
