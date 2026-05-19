import re
import sys

def extract_labourhr_law(html_path, law_name):
    """Extract law text from labourhr.com HTML pages.
    These pages have the law content in a specific div/article structure.
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Check if the content is actually Chinese or garbled
    # The HTML might have the content in a specific tag
    # Try to find the article content container
    
    # Strategy: find the law content between the article header and footer
    # Remove script and style sections
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL)
    
    # Remove all HTML tags but keep text
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'</?p[^>]*>', '\n', text)
    text = re.sub(r'</?div[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    
    # Clean up whitespace
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 2:
            cleaned.append(line)
    text = '\n'.join(cleaned)
    
    # Find the start of the law content
    # The law typically starts with chapter headings
    start_patterns = ['第一章总则', '第一章 总 则', '第一章　总　则', '第一章 总则']
    start_idx = -1
    for pat in start_patterns:
        idx = text.find(pat)
        if idx >= 0:
            start_idx = idx
            break
    
    if start_idx < 0:
        print("Could not find start of law content")
        # Print first 1000 chars for debugging
        print("First 1000 chars of text:")
        print(text[:1000])
        return None, 0
    
    text = text[start_idx:]
    
    # Find where the law content ends
    # Usually there's a footer with "分享到", "验证码", "上一篇" etc.
    end_patterns = ['分享到：', '分享到', '昵称：', '验证码：', '上一篇', '下一篇', '劳动法在线LAODONGFAZAIXIAN']
    end_idx = len(text)
    for pat in end_patterns:
        idx = text.find(pat)
        if 0 < idx < end_idx:
            end_idx = idx
    
    # But make sure we're not cutting too early - the end should be after all law articles
    # For 劳动法, the last article is 第一百零七条
    # For 劳动合同法, the last article is 第九十八条
    last_articles = {
        '劳动法': '第一百零七条',
        '劳动合同法': '第九十八条'
    }
    if law_name in last_articles:
        last_article = last_articles[law_name]
        last_idx = text.rfind(last_article)
        if last_idx > 0:
            # Don't cut before the last article
            end_idx = max(end_idx, last_idx + 100)
    
    text = text[:end_idx].strip()
    
    # Remove any remaining navigation text (lines that are clearly not law content)
    # Keep only lines that are relevant
    final_lines = []
    for line in text.split('\n'):
        line = line.strip()
        # Skip lines that are clearly navigation/UI elements
        if any(skip in line for skip in ['劳动法在线', '课程中心', '法律服务', '企业团报', 
                                           '联系我们', '首页Home', '法律法规Nav',
                                           '@2026', '京ICP备', '京公网安备', '劳动法在线LAODONGFAZAIXIAN']):
            continue
        if line and len(line) > 1:
            final_lines.append(line)
    
    text = '\n'.join(final_lines)
    
    # Count articles
    articles = re.findall(r'第[一二三四五六七八九十百零〇]+条', text)
    
    print(f'Law: {law_name}')
    print(f'Total chars: {len(text)}')
    print(f'Articles found: {len(articles)}')
    print('---FIRST 200---')
    print(text[:200])
    print('---LAST 200---')
    print(text[-200:])
    
    return text, len(articles)

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        html_path = sys.argv[1]
        law_name = sys.argv[2] if len(sys.argv) > 2 else 'unknown'
        extract_labourhr_law(html_path, law_name)
