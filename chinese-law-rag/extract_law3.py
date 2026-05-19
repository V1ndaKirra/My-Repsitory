import re
import sys

def extract_law_from_html(html_path, law_name, output_path):
    """Extract law text from HTML - works with labourhr.com style pages."""
    
    # Read the file, try to detect encoding
    content = None
    for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try:
            with open(html_path, 'r', encoding=encoding) as f:
                content = f.read()
            # Check if content looks like valid Chinese
            if '第一' in content and '条' in content:
                print(f"Successfully read with encoding: {encoding}")
                break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if content is None:
        print("Failed to read file with any encoding")
        return
    
    html = content
    
    # Remove script and style blocks
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Extract text from known HTML patterns
    # labourhr.com uses: <p style="..."><span style="...">TEXT</span></p>
    # Extract all text between <p> tags that contain law articles
    
    # Method: find all <p> tag content, extract text
    p_contents = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    
    # Extract text from spans within p tags
    law_lines = []
    in_law = False
    article_count = 0
    
    for p_html in p_contents:
        # Extract text, removing all HTML tags
        text = re.sub(r'<br\s*/?>', '\n', p_html)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.strip()
        
        if not text:
            continue
        
        # Check if this looks like law content
        # Law articles start with "第X条" or chapter headings
        is_law_content = (
            re.search(r'第[一二三四五六七八九十百零〇]+条', text) or
            re.search(r'第[一二三四五六七八九十]+章', text) or
            '总则' in text[:10] or
            '附则' in text[:10] or
            '目录' in text[:10]
        )
        
        # Also check for law metadata (passed date, etc.)
        is_metadata = (
            '全国人民代表大会' in text or
            '中华人民共和国主席' in text or
            '常务委员会' in text or
            '修正' in text[:20] or
            '通过' in text[:20]
        )
        
        if is_law_content or (in_law and len(text) > 10):
            in_law = True
            law_lines.append(text)
            if re.search(r'第[一二三四五六七八九十百零〇]+条', text):
                article_count += 1
    
    # Remove duplicate lines and clean up
    seen = set()
    unique_lines = []
    for line in law_lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)
    
    # Also try to extract law content more directly
    # Look for the main content div that contains the law
    # The law content is in div.window1 or similar
    
    # Alternative approach: find the section between the law title and footer
    # Try to find the main content area
    content_match = re.search(r'(第一章\s*总\s*则.*?)(?:分享到|验证码|昵称)', html, re.DOTALL)
    if content_match:
        law_text = content_match.group(1)
        # Remove HTML tags
        law_text = re.sub(r'<br\s*/?>', '\n', law_text)
        law_text = re.sub(r'<[^>]+>', '', law_text)
        law_text = re.sub(r'&nbsp;', ' ', law_text)
        law_text = re.sub(r'\n\s*\n+', '\n', law_text)
        law_text = re.sub(r'[ \t]+', ' ', law_text)
        
        lines = [l.strip() for l in law_text.split('\n') if l.strip()]
        law_text = '\n'.join(lines)
        
        articles = re.findall(r'第[一二三四五六七八九十百零〇]+条', law_text)
        print(f"Method 2 - Articles found: {len(articles)}")
        print(f"Total chars: {len(law_text)}")
        
        # Save to file
        title_line = f"{law_name}\n\n"
        full_text = title_line + law_text
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        print(f"Saved {len(articles)} articles to {output_path}")
        return law_text, len(articles)
    
    print(f"Method 1 - Articles found: {article_count}")
    print(f"Lines: {len(unique_lines)}")
    
    # If we got reasonable content, save it
    if article_count > 10:
        full_text = f"{law_name}\n\n" + '\n'.join(unique_lines)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"Saved to {output_path}")
        return '\n'.join(unique_lines), article_count
    
    print("Could not extract enough law content")
    return None, 0


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        extract_law_from_html(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: extract_law3.py <html_path> <law_name> <output_path>")
