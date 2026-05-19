"""
改进版法律提取器 - 使用 BeautifulSoup 类逻辑
"""
import re
import html as html_mod
import os
import json

def clean_html_better(raw):
    """更好的HTML清理 - 保留段落结构"""
    # 移除script和style
    raw = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r'<noscript[^>]*>.*?</noscript>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    
    # 处理特殊标签
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</?p[^>]*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</?div[^>]*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</?tr[^>]*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</?li[^>]*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<hr[^>]*>', '\n---\n', raw, flags=re.IGNORECASE)
    
    # 移除所有剩余的HTML标签
    raw = re.sub(r'<[^>]+>', '', raw)
    
    # HTML实体解码
    text = html_mod.unescape(raw)
    
    # 清理空白
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    return text.strip()

def extract_with_sections(text):
    """提取法律全文，保留章节结构，逐条提取"""
    lines = text.split('\n')
    
    # 找到法律正文开始位置（跳过导航、页头等）
    law_start = 0
    for i, line in enumerate(lines):
        line = line.strip()
        # 找法律标题
        if '中华人民共和国治安管理处罚法' in line and len(line) < 50:
            law_start = i
            break
        if '第一章' in line and '总则' in line:
            law_start = max(0, i - 5)
            break
    
    # 从法律正文开始，找到第一章
    main_text = '\n'.join(lines[law_start:])
    
    # 提取所有"第X条" - 使用更精确的匹配
    # 第X条可能跨行，先规范化
    main_text = re.sub(r'\n+', '\n', main_text)
    
    article_pattern = re.compile(r'(第[一二三四五六七八九十百千零]+条)')
    parts = article_pattern.split(main_text)
    
    # parts[0] = text before first article
    # parts[1] = "第一条", parts[2] = content after 第一条
    # parts[3] = "第二条", parts[4] = content after 第二条
    # etc.
    
    articles = []
    preamble = parts[0] if parts else ''
    
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            header = parts[i]  # e.g., "第一条"
            body = parts[i+1]  # content until next article
        else:
            header = parts[i]
            body = ''
        
        # Extract article number
        num_match = re.match(r'第([一二三四五六七八九十百千零]+)条', header)
        if num_match:
            article_num_cn = num_match.group(1)
            article_num = cn_to_int(article_num_cn)
            if 1 <= article_num <= 5000:
                content = body.strip()
                content = re.sub(r'\s+', ' ', content)
                articles.append({
                    "number": article_num,
                    "header": header,
                    "content": f"{header} {content}"
                })
    
    return preamble, articles

CN_DIGIT = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}

def cn_to_int(s):
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

os.chdir('E:/Hanko-workspace/law_data')

with open('zhianguanlichufafa_raw.html', 'r', encoding='utf-8') as f:
    raw = f.read()

text = clean_html_better(raw)

# Find the law title
lines = text.split('\n')
for i, line in enumerate(lines):
    if '治安管理处罚法' in line and len(line.strip()) < 80:
        print(f'Title line {i}: {line.strip()[:100]}')

# Extract articles
preamble, articles = extract_with_sections(text)
print(f'Extracted {len(articles)} articles')

# Show first few and last few
for a in articles[:5]:
    num = a['number']
    txt = a['content'][:60]
    print(f'  Art {num}: {txt}...')
print('  ...')
for a in articles[-5:]:
    num = a['number']
    txt = a['content'][:60]
    print(f'  Art {num}: {txt}...')

# Save
if articles:
    with open('zhianguanlichufafa_v2.txt', 'w', encoding='utf-8') as f:
        f.write('中华人民共和国治安管理处罚法\n\n')
        # Write preamble (table of contents, etc.)
        f.write(preamble.strip() + '\n\n')
        for a in articles:
            f.write(a['content'] + '\n\n')
    print(f'Saved {len(articles)} articles to zhianguanlichufafa_v2.txt')
