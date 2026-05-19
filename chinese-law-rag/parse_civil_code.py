"""
解析民法典全文 v4 - cn_to_int 彻底修复
"""
import re, json, html as html_mod

with open('civil_code_raw.html', 'r', encoding='utf-8') as f:
    raw = f.read()

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

start_idx = text.find('第一编')
text = text[start_idx:]

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
            if temp == 0:
                temp = 1
            temp *= 10
            result += temp
            temp = 0
        elif char == '百':
            if temp == 0:
                temp = 1
            temp *= 100
            result += temp
            temp = 0
        elif char == '千':
            if temp == 0:
                temp = 1
            temp *= 1000
            result += temp
            temp = 0
        elif char == '零':
            pass  # placeholder
    result += temp
    return result

# 测试
tests = ['一','十','二十','一百','一百零一','一百一十','一百一十一',
         '二百','一千','一千一百','一千一百一十','一千二百三十四',
         '零','一千零一','一千二百','十','八百九十九','一千二百六十']
print("Testing cn_to_int:")
all_ok = True
expected = [1,10,20,100,101,110,111,200,1000,1100,1110,1234,0,1001,1200,10,899,1260]
for t, exp in zip(tests, expected):
    got = cn_to_int(t)
    ok = "OK" if got == exp else f"FAIL (expected {exp})"
    if got != exp:
        all_ok = False
    print(f"  {t} -> {got} {ok}")

if not all_ok:
    print("cn_to_int 仍有错误，请检查！")
    exit(1)
else:
    print("cn_to_int 全部正确！")

# 提取层级标题
lines = text.split('\n')
hier_positions = []

for i, line in enumerate(lines):
    line = line.strip()
    if not line:
        continue
    m_book = re.match(r'(第[一二三四五六七八九十]+编)\s*(.*)', line)
    if m_book:
        hier_positions.append((i, 'book', m_book.group(1), m_book.group(2).strip()))
        continue
    m_ch = re.match(r'(第[一二三四五六七八九十]+章)\s*(.*)', line)
    if m_ch:
        hier_positions.append((i, 'chapter', m_ch.group(1), m_ch.group(2).strip()))
        continue
    m_sec = re.match(r'(第[一二三四五六七八九十]+节)\s*(.*)', line)
    if m_sec:
        hier_positions.append((i, 'section', m_sec.group(1), m_sec.group(2).strip()))

# 找到所有条文
article_headers = list(re.finditer(r'第([一二三四五六七八九十百千零]+)条\s*', text))
print(f"找到 {len(article_headers)} 个条文标题")

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
    
    if article_num > 2000 or article_num < 1:
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
        "ref": f"《中华人民共和国民法典》{book_title} {chapter_title} {section_title} 第{article_num_cn}条".replace("  ", " ").strip()
    })

# 去重
unique = {}
for a in articles:
    if a['number'] not in unique:
        unique[a['number']] = a
articles = sorted(unique.values(), key=lambda x: x['number'])
print(f"去重后: {len(articles)} 条（民法典应有1260条）")

with open('civil_code_articles.json', 'w', encoding='utf-8') as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

with open('civil_code_articles.txt', 'w', encoding='utf-8') as f:
    for a in articles:
        f.write(f"[第{a['number']}条] {a['ref']}\n{a['content']}\n\n")

print("Saved!")
print(f"条文范围: 第{articles[0]['number']}条 ~ 第{articles[-1]['number']}条")

# 验证关键条款
key = [944, 937, 938, 939, 940, 941, 942, 943]
for a in articles:
    if a['number'] in key:
        print(f"\n=== 第{a['number']}条 ===")
        print(f"  {a['ref']}")
        print(f"  {a['content'][:120]}...")
