"""
法律知识库构建脚本
1. 加载所有已解析的法律条文 JSON
2. 使用 SiliconFlow BGE API 进行向量化
3. 存入 ChromaDB
4. 提供检索接口
"""
import json, os, glob, time
import chromadb
from chromadb.utils import embedding_functions
import requests

# ============================================================
# 配置
# ============================================================
DATA_DIR = r'E:\Hanko-workspace\law_data'
DB_DIR = r'E:\Hanko-workspace\law_db'

# SiliconFlow API 配置
SILICONFLOW_API_KEY = os.environ['SILICONFLOW_API_KEY']
SILICONFLOW_BASE_URL = 'https://api.siliconflow.cn/v1'

# BGE 模型
EMBEDDING_MODEL = 'BAAI/bge-large-zh-v1.5'

# ============================================================
# 1. 加载所有法律条文
# ============================================================
def load_all_articles():
    """加载 DATA_DIR 下所有 *_articles.json 和 *.json 文件"""
    all_articles = []
    json_files = glob.glob(os.path.join(DATA_DIR, '*.json'))
    
    for f in json_files:
        # 跳过原始文件
        basename = os.path.basename(f)
        if 'raw' in basename.lower():
            continue
        
        with open(f, 'r', encoding='utf-8') as fp:
            try:
                data = json.load(fp)
                if isinstance(data, list):
                    law_name = data[0].get('law', basename.replace('.json', '')) if data else basename
                    print(f"  加载 {basename}: {len(data)} 条 ({law_name})")
                    all_articles.extend(data)
            except:
                print(f"  跳过 {basename}（格式不匹配）")
    
    print(f"\n总计: {len(all_articles)} 条法律条文")
    
    # 统计
    laws = {}
    for a in all_articles:
        law = a.get('law', '未知')
        laws[law] = laws.get(law, 0) + 1
    for law, count in sorted(laws.items()):
        print(f"  {law}: {count} 条")
    
    return all_articles

# ============================================================
# 2. Embedding 函数（调用 SiliconFlow API）
# ============================================================
def embed_texts(texts, api_key=None, batch_size=20):
    """
    调用 SiliconFlow BGE API 批量向量化
    texts: 字符串列表
    返回: 向量列表
    """
    if api_key is None:
        api_key = SILICONFLOW_API_KEY
    
    if not api_key:
        raise ValueError("请设置 SILICONFLOW_API_KEY 环境变量或在代码中填写")
    
    url = f"{SILICONFLOW_BASE_URL}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    all_embeddings = []
    total = len(texts)
    
    for i in range(0, total, batch_size):
        batch = texts[i:i+batch_size]
        payload = {
            "model": EMBEDDING_MODEL,
            "input": batch,
            "encoding_format": "float"
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            print(f"  API 错误: {resp.status_code} {resp.text[:200]}")
            raise Exception(f"Embedding API failed: {resp.text}")
        
        result = resp.json()
        embeddings = [item['embedding'] for item in sorted(result['data'], key=lambda x: x['index'])]
        all_embeddings.extend(embeddings)
        
        progress = min(i + batch_size, total)
        print(f"  向量化进度: {progress}/{total}")
        
        # 避免速率限制
        if i + batch_size < total:
            time.sleep(0.1)
    
    return all_embeddings

# ============================================================
# 3. 构建 ChromaDB
# ============================================================
def build_database(articles, api_key=None):
    """构建 ChromaDB 法律知识库"""
    
    # 创建 ChromaDB 客户端
    client = chromadb.PersistentClient(path=DB_DIR)
    
    # 删除旧集合（如果存在）
    try:
        client.delete_collection("chinese_laws")
    except:
        pass
    
    collection = client.create_collection(
        name="chinese_laws",
        metadata={"description": "中国法律法规知识库"}
    )
    
    # 准备数据
    print(f"\n准备向量化 {len(articles)} 条法律条文...")
    texts = [a['content'] for a in articles]
    
    # 调用 API 进行向量化
    print(f"正在调用 {EMBEDDING_MODEL} 进行向量化...")
    embeddings = embed_texts(texts, api_key)
    
    # 准备元数据
    ids = []
    metadatas = []
    documents = []
    
    for i, a in enumerate(articles):
        # 生成唯一 ID
        law_short = a.get('law', 'unknown')[:20]
        article_id = f"{law_short}_{a['number']}"
        ids.append(article_id)
        
        # 元数据（支持过滤检索）
        metadatas.append({
            "law": a.get('law', ''),
            "article_number": a['number'],
            "book": a.get('book', ''),
            "chapter": a.get('chapter', ''),
            "section": a.get('section', ''),
            "ref": a.get('ref', ''),
        })
        
        documents.append(a['content'])
    
    # 批量写入 ChromaDB
    print(f"\n写入 ChromaDB...")
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
            documents=documents[i:end]
        )
        print(f"  写入进度: {end}/{len(ids)}")
    
    print(f"\n✅ 数据库构建完成！共 {len(ids)} 条记录")
    print(f"数据库路径: {DB_DIR}")
    
    return collection

# ============================================================
# 4. 检索测试
# ============================================================
def search_law(collection, query, api_key=None, top_k=5):
    """检索相关法律条文"""
    if api_key is None:
        api_key = SILICONFLOW_API_KEY
    
    # 向量化查询
    url = f"{SILICONFLOW_BASE_URL}/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={
        "model": EMBEDDING_MODEL,
        "input": [query],
    })
    query_embedding = resp.json()['data'][0]['embedding']
    
    # 检索
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    
    return results

# ============================================================
# 主流程
# ============================================================
if __name__ == '__main__':
    import sys
    
    api_key = SILICONFLOW_API_KEY
    if not api_key:
        api_key = input("请输入 SiliconFlow API Key: ").strip()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'search':
        # 检索模式
        if len(sys.argv) < 3:
            print("用法: python build_law_db.py search <查询文本>")
            sys.exit(1)
        
        query = sys.argv[2]
        client = chromadb.PersistentClient(path=DB_DIR)
        collection = client.get_collection("chinese_laws")
        results = search_law(collection, query, api_key)
        
        print(f"\n查询: {query}")
        print("=" * 60)
        for i in range(len(results['documents'][0])):
            dist = results['distances'][0][i]
            meta = results['metadatas'][0][i]
            doc = results['documents'][0][i]
            print(f"\n[{i+1}] 距离: {dist:.4f}")
            print(f"    法律: {meta['law']}")
            print(f"    位置: {meta.get('ref', '')}")
            print(f"    内容: {doc[:200]}...")
    else:
        # 构建模式
        articles = load_all_articles()
        if not articles:
            print("未找到任何法律条文！")
            sys.exit(1)
        
        collection = build_database(articles, api_key)
        
        # 测试检索
        print("\n" + "=" * 60)
        print("测试检索")
        print("=" * 60)
        
        test_queries = [
            "业主未入住是否需要缴纳物业费",
            "正当防卫的构成要件",
            "劳动合同解除的补偿标准",
        ]
        
        for q in test_queries:
            results = search_law(collection, q, api_key, top_k=3)
            print(f"\n查询: {q}")
            for i in range(len(results['documents'][0])):
                meta = results['metadatas'][0][i]
                dist = results['distances'][0][i]
                doc = results['documents'][0][i]
                print(f"  [{i+1}] dist={dist:.4f} | {meta.get('law','')} 第{meta['article_number']}条")
                print(f"       {doc[:120]}...")
