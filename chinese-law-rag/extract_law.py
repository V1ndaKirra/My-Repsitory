import re
import sys

def extract_law_text(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 1:
            cleaned.append(line)
    text = '\n'.join(cleaned)
    
    # Try different start markers
    start_markers = ['第一章总则', '第一章 总 则', '第一章　总　则', '第一章 总则']
    for marker in start_markers:
        idx = text.find(marker)
        if idx > 0:
            text = text[idx:]
            break
    
    # Remove everything after footer patterns
    end_patterns = ['分享到', '昵称', '验证码', '劳动法在线', '上一篇', '下一篇']
    for pat in end_patterns:
        idx = text.rfind(pat)
        if idx > 0 and idx > len(text) * 0.7:  # only if near the end
            text = text[:idx]
            break
    
    # Count articles
    articles = re.findall(r'第[一二三四五六七八九十百零〇]+条', text)
    print(f'Total chars: {len(text)}')
    print(f'Articles found: {len(articles)}')
    print('---FIRST 300---')
    print(text[:300])
    print('---LAST 300---')
    print(text[-300:])
    
    return text, len(articles)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        extract_law_text(sys.argv[1])
