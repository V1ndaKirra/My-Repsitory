"""
TXT 格式法律文本解析器（GBK/UTF-8 自动检测）
支持格式：第X条　【标签】内容  或  第X条 内容
"""
import re, json, sys, os
sys.path.insert(0, '.')
from parse_civil_code import cn_to_int

def parse_txt_law(text, law_name):
    """解析 TXT 格式的法律文本"""
    lines = text.split('\n')
    articles = []
    
    book = ''
    chapter = ''
    section = ''
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 层级标题（第一编 / 第一章 / 第一节）
        m_book = re.match(r'(第[一二三四五六七八九十]+编)\s+(.+)', line)
        if m_book:
            book = f"{m_book.group(1)} {m_book.group(2)}"
            chapter = ''
            section = ''
            continue
        
        m_ch = re.match(r'(第[一二三四五六七八九十]+章)\s+(.+)', line)
        if m_ch:
            chapter = f"{m_ch.group(1)} {m_ch.group(2)}"
            section = ''
            continue
        
        m_sec = re.match(r'(第[一二三四五六七八九十]+节)\s+(.+)', line)
        if m_sec:
            section = f"{m_sec.group(1)} {m_sec.group(2)}"
            continue
        
        # 条文：第X条[　 ]【标签】内容  或  第X条 内容
        # 支持全角空格(\u3000)和半角空格
        m = re.match(r'第([一二三四五六七八九十百千零]+)条(?:\s*之[一二三])?[\s\u3000]*(?:【[^】]*】)?[\s\u3000]*(.+)', line)
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
                'law': law_name,
                'ref': f'《{law_name}》{book} {chapter} {section} 第{num_cn}条'.replace('  ', ' ').strip()
            })
    
    # 去重
    unique = {}
    for a in articles:
        if a['number'] not in unique:
            unique[a['number']] = a
    return sorted(unique.values(), key=lambda x: x['number'])

def process_law(input_file, law_name, output_prefix=None):
    """处理一部法律：自动检测编码 → 解析 → 保存"""
    if output_prefix is None:
        output_prefix = os.path.splitext(input_file)[0]
    
    # 读取并自动检测编码
    with open(input_file, 'rb') as f:
        raw = f.read()
    
    # 尝试多种编码
    for enc in ['utf-8', 'gbk', 'gb18030', 'gb2312']:
        try:
            text = raw.decode(enc)
            # 验证：检查是否有"第X条"模式
            if '第' in text and '条' in text:
                print(f"  Encoding: {enc}")
                break
        except:
            continue
    else:
        print(f"  ERROR: Cannot decode {input_file}")
        return None
    
    articles = parse_txt_law(text, law_name)
    print(f"  解析完成: {len(articles)} 条")
    
    if not articles:
        return None
    
    # 保存 JSON
    json_file = f"{output_prefix}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    # 保存 TXT
    txt_file = f"{output_prefix}_parsed.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for a in articles:
            f.write(f"[第{a['number']}条] {a['ref']}\n{a['content']}\n\n")
    
    print(f"  已保存: {json_file}")
    print(f"  条文范围: 第{articles[0]['number']}条 ~ 第{articles[-1]['number']}条")
    return articles

if __name__ == '__main__':
    # 处理刑法
    print("=" * 50)
    print("处理: 中华人民共和国刑法")
    process_law('criminal_law_gbk.txt', '中华人民共和国刑法', 'criminal_law')
    
    # 也可以从命令行参数批量处理
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            name = os.path.basename(f).replace('_', ' ')
            process_law(f, name)
