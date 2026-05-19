"""
批量下载第二批法律全文
从 gov.cn 等官方站点抓取并提取纯文本
"""
import re
import html as html_mod
import os
import sys
import urllib.request
import urllib.error
import json

CN_DIGIT = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}

def cn_to_int(s):
    """中文数字转整数"""
    s = s.strip()
    result = 0
    temp = 0
    for char in s:
        if char in CN_DIGIT:
            temp = CN_DIGIT[char]
        elif char == '十':
            if temp == 0: temp = 1
            temp *= 10; result += temp; temp = 0
        elif char == '百':
            if temp == 0: temp = 1
            temp *= 100; result += temp; temp = 0
        elif char == '千':
            if temp == 0: temp = 1
            temp *= 1000; result += temp; temp = 0
        elif char == '零':
            pass
    result += temp
    return result

def clean_html(raw):
    """清理HTML"""
    raw = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def extract_articles(text, law_name):
    """提取条文"""
    # 更宽松的匹配：第X条 后面可能跟空格、标点或各种内容
    article_headers = list(re.finditer(r'第([一二三四五六七八九十百千零]+)条\s*', text))
    
    articles = []
    for idx, m in enumerate(article_headers):
        article_num_cn = m.group(1)
        article_start = m.end()
        
        if idx + 1 < len(article_headers):
            article_end = article_headers[idx + 1].start()
        else:
            article_end = len(text)
        
        content_raw = text[article_start:article_end].strip()
        content_raw = re.sub(r'\s+', ' ', content_raw)
        
        article_num = cn_to_int(article_num_cn)
        if article_num > 5000 or article_num < 1:
            continue
        
        full_content = f"第{article_num_cn}条 {content_raw}"
        articles.append({
            "number": article_num,
            "content": full_content
        })
    
    # 去重并排序
    unique = {}
    for a in articles:
        if a['number'] not in unique:
            unique[a['number']] = a
    articles = sorted(unique.values(), key=lambda x: x['number'])
    return articles

def download_url(url, timeout=30):
    """下载URL内容"""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"    下载失败: {e}")
        return None

def process_law(url, law_name, filename_base):
    """处理一部法律"""
    print(f"\n========================================")
    print(f"处理: {law_name}")
    print(f"来源: {url}")
    
    # 先尝试本地文件
    raw_file = f"{filename_base}_raw.html"
    raw_html = None
    
    if os.path.exists(raw_file):
        print(f"  找到本地缓存: {raw_file}")
        with open(raw_file, 'r', encoding='utf-8') as f:
            raw_html = f.read()
    else:
        print(f"  正在下载...")
        raw_html = download_url(url)
        if raw_html:
            with open(raw_file, 'w', encoding='utf-8') as f:
                f.write(raw_html)
            print(f"  已保存缓存: {raw_file}")
    
    if not raw_html:
        print("  失败: 无法获取内容")
        return None
    
    text = clean_html(raw_html)
    
    # 找到法律名称之后的内容
    # 尝试各种名称变体
    name_patterns = [
        re.escape(law_name),
        re.escape(law_name.replace('中华人民共和国', '')),
    ]
    
    # 提取标题之后的正文
    articles = extract_articles(text, law_name)
    print(f"  提取到 {len(articles)} 条条文")
    
    if not articles:
        # 尝试更宽松的匹配
        print("  尝试宽松匹配...")
        # 尝试找所有 "第X条"
        all_art = list(re.finditer(r'第([一二三四五六七八九十百千零]+)条', text))
        print(f"  宽松匹配找到 {len(all_art)} 处'第X条'")
        articles = extract_articles(text, law_name)
    
    if articles:
        # 保存为TXT
        txt_file = f"{filename_base}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"{law_name}\n\n")
            for a in articles:
                f.write(f"{a['content']}\n\n")
        print(f"  已保存: {txt_file} ({len(articles)}条)")
        
        # 保存JSON
        json_file = f"{filename_base}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"  已保存: {json_file}")
        
        return articles
    else:
        print("  警告: 未提取到条文，保存原始文本")
        txt_file = f"{filename_base}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"{law_name}\n\n{text}")
        return None

# ============================================================
# 第一批：处理已下载的原始文件
# ============================================================
os.chdir('E:/Hanko-workspace/law_data')

# 治安管理处罚法 - 已有原始文件
process_law(
    "https://jyglj.guizhou.gov.cn/lps/jywh/202601/t20260119_89309289.html",
    "中华人民共和国治安管理处罚法",
    "zhianguanlichufafa"
)

print("\n\n完成治安管理处罚法处理")
