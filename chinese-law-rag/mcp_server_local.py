"""
中国法律知识库 MCP Server (本地版)
FastMCP 实现，自带 HTTP/SSE 服务器
"""
import os, chromadb, requests
from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get('LAW_DB_PATH', r'E:\Hanko-workspace\law_db')
API_KEY = os.environ['SILICONFLOW_API_KEY']
MODEL = 'BAAI/bge-large-zh-v1.5'
PORT = int(os.environ.get('MCP_PORT', '8765'))

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_collection('chinese_laws')
print(f'[MCP] 知识库已加载: {collection.count()} 条法律条文')

mcp = FastMCP('chinese-law-mcp', host='127.0.0.1', port=PORT)

def embed(q):
    r = requests.post('https://api.siliconflow.cn/v1/embeddings',
        headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
        json={'model': MODEL, 'input': [q]}, timeout=30)
    return r.json()['data'][0]['embedding']

@mcp.tool()
def search_law(query: str, top_k: int = 5) -> str:
    """搜索中国法律法规。输入自然语言问题，返回最相关的法律条文原文及出处。例如：业主未入住是否需要缴纳物业费"""
    emb = embed(query)
    results = collection.query(
        query_embeddings=[emb], n_results=top_k,
        include=['documents', 'metadatas', 'distances']
    )
    lines = [f'查询：{query}', f'知识库共 {collection.count()} 条法律条文', '']
    for i in range(len(results['documents'][0])):
        m = results['metadatas'][0][i]
        d = results['documents'][0][i]
        dist = results['distances'][0][i]
        lines.append(f"#{i+1} 《{m['law']}》第{m['article_number']}条（相关性：{1-dist:.2f}）")
        lines.append(d)
        lines.append('')
    return '\n'.join(lines)

@mcp.tool()
def get_article(law_name: str, article_number: int) -> str:
    """获取指定法律的特定条文原文。"""
    results = collection.get(include=['documents', 'metadatas'])
    if results['metadatas']:
        for i, m in enumerate(results['metadatas']):
            if m.get('law') == law_name and m.get('article_number') == article_number:
                return f"《{law_name}》第{article_number}条\n{results['documents'][i]}"
    return f"未找到《{law_name}》第{article_number}条。当前知识库：民法典(1260条)、刑法(451条)"

if __name__ == '__main__':
    print(f'[MCP] 启动 SSE 服务器，端口 {PORT}')
    print(f'[MCP] 端点: http://localhost:{PORT}/sse')
    mcp.run(transport='sse')
