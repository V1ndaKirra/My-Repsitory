"""
Markdown 格式法律文本解析器
适用于 web_fetch 输出的 markdown 格式法律全文
"""
import re, json, sys
sys.path.insert(0, '.')
from parse_civil_code import cn_to_int  # 复用数字转换函数

def parse_markdown_law(md_text, law_name):
    """解析 markdown 格式的法律文本为结构化条文"""
    lines = md_text.split('\n')
    articles = []
    
    book = ''
    chapter = ''
    section = ''
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 层级标题
        if line.startswith('## '):
            book = line[3:].strip()
            chapter = ''
            section = ''
            continue
        if line.startswith('### '):
            chapter = line[4:].strip()
            section = ''
            continue
        if line.startswith('#### '):
            section = line[5:].strip()
            continue
        
        # 条文格式: 第X条 【标签】内容  或  第X条 内容  或  第X条之X
        m = re.match(r'第([一二三四五六七八九十百千零]+)条(?:\s*之[一二三])?\s*(?:【[^】]*】)?\s*(.*)', line)
        if m:
            num_cn = m.group(1)
            content = m.group(2).strip() if m.group(2) else ''
            
            num = cn_to_int(num_cn)
            if num < 1 or num > 5000:
                continue
            
            full = f'第{num_cn}条 {content}'
            articles.append({
                'number': num,
                'content': full,
                'book': book,
                'chapter': chapter,
                'section': section,
                'law': law_name
            })
    
    # 去重
    unique = {}
    for a in articles:
        if a['number'] not in unique:
            unique[a['number']] = a
    return sorted(unique.values(), key=lambda x: x['number'])

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python parse_markdown_law.py <input.md> <law_name> [output_prefix]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    law_name = sys.argv[2]
    output_prefix = sys.argv[3] if len(sys.argv) > 3 else input_file.replace('.md', '').replace('.txt', '')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    articles = parse_markdown_law(text, law_name)
    print(f"解析完成: {len(articles)} 条")
    
    # 保存 JSON
    json_file = f"{output_prefix}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    # 保存 TXT
    txt_file = f"{output_prefix}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for a in articles:
            ref_parts = [a['law'], a['book'], a['chapter'], a['section']]
            ref = ' '.join(p for p in ref_parts if p)
            f.write(f"[第{a['number']}条] {ref}\n{a['content']}\n\n")
    
    print(f"已保存: {json_file}, {txt_file}")
    print(f"条文范围: 第{articles[0]['number']}条 ~ 第{articles[-1]['number']}条")
