"""
微信公众号股票助手 - Flask 回调服务
功能: 添加/删除/查看自选股，生成盘前简报
"""

import os
import re
import time
import hashlib
import sqlite3
import threading
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Flask, request, make_response
import requests

app = Flask(__name__)

# ============================================================
# 配置
# ============================================================

WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "hanako_stock_bot_2026")
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
TUSHARE_URL = "http://api.tushare.pro"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wechat_bot.db")

# 股票简称映射（常用）
STOCK_NAMES = {
    "000001.SZ": "平安银行", "600519.SH": "贵州茅台", "000858.SZ": "五粮液",
    "300750.SZ": "宁德时代", "002594.SZ": "比亚迪", "000002.SZ": "万科A",
    "600036.SH": "招商银行", "000651.SZ": "格力电器", "600900.SH": "长江电力",
    "300059.SZ": "东方财富", "002415.SZ": "海康威视", "600276.SH": "恒瑞医药",
}

# ============================================================
# 数据库
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            openid TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT DEFAULT '',
            added_at TEXT NOT NULL,
            UNIQUE(openid, stock_code)
        )
    """)
    conn.commit()
    return conn

# ============================================================
# Tushare API
# ============================================================

def get_stock_name(code):
    """获取股票简称"""
    if code in STOCK_NAMES:
        return STOCK_NAMES[code]
    try:
        resp = requests.post(TUSHARE_URL, json={
            "api_name": "stock_basic",
            "token": TUSHARE_TOKEN,
            "params": {"ts_code": code},
            "fields": "ts_code,name"
        }, timeout=5)
        data = resp.json()
        if data.get("code") == 0 and data["data"]["items"]:
            name = data["data"]["items"][0][1]
            STOCK_NAMES[code] = name
            return name
    except:
        pass
    return code


def get_suspend_info(codes):
    """获取停复牌信息"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        month_ago = (datetime.now().replace(day=1)).strftime("%Y%m%d")
        resp = requests.post(TUSHARE_URL, json={
            "api_name": "suspend_d",
            "token": TUSHARE_TOKEN,
            "params": {
                "ts_code": ",".join(codes),
                "start_date": month_ago,
                "end_date": today,
            },
            "fields": "ts_code,trade_date,suspend_type"
        }, timeout=8)
        data = resp.json()
        if data.get("code") != 0:
            return []
        
        # 找每只股票最新状态
        latest = {}
        for item in data["data"]["items"]:
            code, date, stype = item[0], item[1], item[2]
            if code not in latest or date > latest[code][0]:
                latest[code] = (date, stype)
        
        return [(code, date, stype) for code, (date, stype) in latest.items() if stype == "S"]
    except:
        return []


def generate_briefing(codes):
    """生成简报"""
    if not codes:
        return "请先添加自选股，发送「添加 代码」开始。"
    
    lines = ["📊 自选股简报", ""]
    lines.append(f"共 {len(codes)} 只自选股")
    
    # 停复牌
    suspends = get_suspend_info(codes)
    if suspends:
        lines.append("\n⏸ 当前停牌:")
        for code, date, _ in suspends[:5]:
            name = get_stock_name(code)
            lines.append(f"  {name}({code})")
    
    # 快速报价（如果有数据源的话，这里简化）
    lines.append(f"\n⏰ {datetime.now().strftime('%H:%M')}")
    return "\n".join(lines)

# ============================================================
# 命令处理
# ============================================================

def handle_command(openid, text):
    """解析并执行用户命令"""
    text = text.strip()
    conn = get_db()
    
    # 添加股票: 添加 <code> 或 添加 <code> <name>
    m = re.match(r'^(添加|add)\s+(\d{6}\.(SZ|SH|BJ))(?:\s+(.+))?', text, re.IGNORECASE)
    if m:
        code = m.group(2).upper()
        name = m.group(4) or get_stock_name(code)
        
        cur = conn.execute("SELECT COUNT(*) FROM watchlist WHERE openid=? AND stock_code=?", (openid, code))
        if cur.fetchone()[0] > 0:
            return f"⚠️ {name}({code}) 已在自选股中"
        
        conn.execute(
            "INSERT OR REPLACE INTO watchlist (openid, stock_code, stock_name, added_at) VALUES (?,?,?,?)",
            (openid, code, name, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return f"✅ 已添加 {name}({code})"
    
    # 删除股票: 删除 <code> 或 删除 <name>
    m = re.match(r'^(删除|移除|del|remove)\s+(.+)$', text, re.IGNORECASE)
    if m:
        keyword = m.group(2).strip().upper()
        
        # 先按代码匹配
        cur = conn.execute("SELECT stock_code, stock_name FROM watchlist WHERE openid=? AND (stock_code=? OR UPPER(stock_name)=?)",
                          (openid, keyword, keyword))
        rows = cur.fetchall()
        if rows:
            code, name = rows[0]
            conn.execute("DELETE FROM watchlist WHERE openid=? AND stock_code=?", (openid, code))
            conn.commit()
            conn.close()
            return f"🗑 已删除 {name}({code})"
        
        # 模糊匹配
        cur = conn.execute("SELECT stock_code, stock_name FROM watchlist WHERE openid=? AND (stock_code LIKE ? OR stock_name LIKE ?)",
                          (openid, f"%{keyword}%", f"%{keyword}%"))
        rows = cur.fetchall()
        if len(rows) == 1:
            code, name = rows[0]
            conn.execute("DELETE FROM watchlist WHERE openid=? AND stock_code=?", (openid, code))
            conn.commit()
            conn.close()
            return f"🗑 已删除 {name}({code})"
        elif len(rows) > 1:
            names = ", ".join([f"{n}({c})" for c, n in rows])
            conn.close()
            return f"找到多个匹配: {names}\n请用代码精确指定，如「删除 000001.SZ」"
        
        conn.close()
        return f"未找到「{keyword}」，请检查代码或名称。"
    
    # 查看列表
    if text in ['列表', 'list', '自选', '持仓', '查看']:
        cur = conn.execute("SELECT stock_code, stock_name FROM watchlist WHERE openid=?", (openid,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return "📭 自选股为空\n发送「添加 代码」开始构建你的自选股\n例如: 添加 000001.SZ"
        
        lines = [f"📋 我的自选 ({len(rows)} 只)"]
        for code, name in rows:
            lines.append(f"  {name}({code})")
        lines.append("\n发送「删除 代码」移除")
        lines.append("发送「简报」查看概况")
        return "\n".join(lines)
    
    # 简报
    if text in ['简报', 'briefing', '盘前', '概况']:
        cur = conn.execute("SELECT stock_code FROM watchlist WHERE openid=?", (openid,))
        codes = [row[0] for row in cur.fetchall()]
        conn.close()
        return generate_briefing(codes)
    
    # 帮助
    if text in ['帮助', 'help', '?', '？']:
        conn.close()
        return """🤖 股票助手使用说明

📌 添加自选股
  添加 000001.SZ
  添加 600519.SH 茅台

🗑 删除自选股
  删除 000001.SZ
  删除 茅台

📋 查看自选股
  列表

📊 生成简报
  简报

❓ 帮助
  帮助"""
    
    conn.close()
    return f"未识别的命令: {text}\n发送「帮助」查看可用命令。"

# ============================================================
# 微信消息处理
# ============================================================

def parse_wechat_xml(xml_data):
    """解析微信消息 XML"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_data)
    msg = {}
    for child in root:
        msg[child.tag] = child.text
    return msg


def build_reply_xml(to_user, from_user, content):
    """构建回复 XML（手动，因为 CDATA 必须用字符串拼接）"""
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


@app.route('/wechat', methods=['GET', 'POST'])
def wechat():
    if request.method == 'GET':
        # Token 验证
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        
        tmp = sorted([WECHAT_TOKEN, timestamp, nonce])
        tmp_str = ''.join(tmp)
        calc = hashlib.sha1(tmp_str.encode()).hexdigest()
        
        if calc == signature:
            return echostr
        return 'verification failed'
    
    # POST: 接收消息
    try:
        msg = parse_wechat_xml(request.data)
        msg_type = msg.get('MsgType', '')
        from_user = msg.get('FromUserName', '')
        to_user = msg.get('ToUserName', '')
        
        if msg_type == 'text':
            content = msg.get('Content', '')
            reply_text = handle_command(from_user, content)
        elif msg_type == 'event':
            event = msg.get('Event', '')
            if event == 'subscribe':
                reply_text = "👋 欢迎使用股票助手！\n\n发送「添加 代码」开始构建你的自选股\n例如: 添加 000001.SZ\n\n发送「帮助」查看所有命令。"
            else:
                reply_text = ""
        else:
            reply_text = "暂不支持此消息类型，请发送文字命令。\n发送「帮助」查看可用命令。"
        
        if reply_text:
            xml = build_reply_xml(to_user, from_user, reply_text)
            response = make_response(xml)
            response.headers['Content-Type'] = 'application/xml'
            return response
        
        return 'success'
    
    except Exception as e:
        print(f"Error: {e}")
        return 'success'


@app.route('/ping')
def ping():
    return 'ok'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
