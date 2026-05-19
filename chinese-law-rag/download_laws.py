"""
通用法律法规下载脚本
支持多种来源：court.gov.cn, xingfa.org, gov.cn 等
"""
import requests, re, json, html as html_mod, os, sys

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

CN_DIGIT = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}

def cn_to_int(s):
    """中文数字字符串转整数"""
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
    """清理HTML并提取纯文本"""
    raw = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    body_match = re.search(r'<body[^>]*>(.*?)</body>', raw, re.DOTALL)
    content = body_match.group(1) if body_match else raw
    text = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text

def parse_articles(text, law_name):
    """从法律文本中提取逐条条文"""
    lines = text.split('\n')
    
    # 提取层级标题
    hier_positions = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        for pattern, htype in [
            (r'(第[一二三四五六七八九十]+编)\s*(.*)', 'book'),
            (r'(第[一二三四五六七八九十]+章)\s*(.*)', 'chapter'),
            (r'(第[一二三四五六七八九十]+节)\s*(.*)', 'section'),
        ]:
            m = re.match(pattern, line)
            if m:
                hier_positions.append((i, htype, m.group(1), m.group(2).strip()))
                break
    
    # 找到所有条文
    article_headers = list(re.finditer(r'第([一二三四五六七八九十百千零]+)条\s*', text))
    print(f"  找到 {len(article_headers)} 个条文标题")
    
    line_starts = []
    pos = 0
    for line in lines:
        line_starts.append(pos)
        pos += len(line) + 1
    
    articles = []
    book_title = chapter_title = section_title = ""
    
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
        
        char_pos = m.start()
        line_num = 0
        for i, ls in enumerate(line_starts):
            if ls > char_pos:
                line_num = i - 1
                break
        else:
            line_num = len(lines) - 1
        
        for ln, htype, hid, htitle in hier_positions:
            if ln < line_num:
                if htype == 'book':
                    book_title = f"{hid} {htitle}"
                    chapter_title = ""
                    section_title = ""
                elif htype == 'chapter':
                    chapter_title = f"{hid} {htitle}"
                    section_title = ""
                elif htype == 'section':
                    section_title = f"{hid} {htitle}"
        
        full_content = f"第{article_num_cn}条 {content_raw}"
        
        articles.append({
            "number": article_num,
            "content": full_content,
            "book": book_title,
            "chapter": chapter_title,
            "section": section_title,
            "law": law_name
        })
    
    # 去重
    unique = {}
    for a in articles:
        if a['number'] not in unique:
            unique[a['number']] = a
    articles = sorted(unique.values(), key=lambda x: x['number'])
    print(f"  去重后: {len(articles)} 条")
    return articles

def download_and_parse(url, law_name, filename):
    """下载并解析一部法律"""
    print(f"\n{'='*50}")
    print(f"下载: {law_name}")
    print(f"URL: {url}")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}，跳过")
            return None
        
        # 保存原始文件
        raw_file = f"{filename}_raw.html"
        with open(raw_file, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        
        text = clean_html(resp.text)
        articles = parse_articles(text, law_name)
        
        if articles:
            # 保存JSON
            json_file = f"{filename}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            
            # 保存纯文本
            txt_file = f"{filename}.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                for a in articles:
                    ref_parts = [a['law'], a['book'], a['chapter'], a['section']]
                    ref = ' '.join(p for p in ref_parts if p)
                    f.write(f"[第{a['number']}条] {ref}\n{a['content']}\n\n")
            
            print(f"  已保存 {json_file} ({len(articles)}条)")
            return articles
        else:
            print("  未提取到条文")
            return None
    except Exception as e:
        print(f"  错误: {e}")
        return None

# ============================================================
# 法律列表
# ============================================================
laws_to_download = [
    {
        "url": "http://xingfa.org/",
        "name": "中华人民共和国刑法",
        "file": "criminal_law"
    },
    {
        "url": "https://www.gov.cn/zwgk/2005-05/23/content_154.htm",
        "name": "物业管理条例",
        "file": "property_management_regulations"
    },
    # 更多法律可以在这里添加
]

for law in laws_to_download:
    download_and_parse(law['url'], law['name'], law['file'])

print("\n\n全部完成!")
print(f"工作目录: {os.getcwd()}")
for f in os.listdir('.'):
    if f.endswith('.json') and f != 'civil_code_articles.json':
        print(f"  {f}")
