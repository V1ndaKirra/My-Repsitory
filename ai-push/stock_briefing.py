"""
盘前简报 - VPS 版 (Tushare → Server酱推送)
运行: TUSHARE_TOKEN=xxx python stock_briefing.py
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta

import requests

# ============================================================
# 配置
# ============================================================

TUSHARE_URL = "http://api.tushare.pro"
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

# 自选股（从旧脚本迁移）
WATCHLIST = [
    "000001.SZ", "600519.SH", "000858.SZ", "300750.SZ", "002594.SZ",
]

NAME_MAP = {
    "000001.SZ": "平安银行", "600519.SH": "贵州茅台", "000858.SZ": "五粮液",
    "300750.SZ": "宁德时代", "002594.SZ": "比亚迪",
}

FORECAST_LABEL = {
    "预增": "🟢", "略增": "🟢", "续盈": "⚪", "扭亏": "🟢",
    "预减": "🔴", "略减": "🟡", "首亏": "🔴", "续亏": "🔴",
    "不确定": "⚪",
}

SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")

# ============================================================
# Tushare API 调用
# ============================================================

def call_tushare(api_name: str, params: dict = None, fields: str = ""):
    payload = {
        "api_name": api_name,
        "token": TUSHARE_TOKEN,
        "params": params or {},
        "fields": fields,
    }
    resp = requests.post(TUSHARE_URL, json=payload, timeout=30)
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"Tushare [{api_name}]: {result.get('msg', '未知错误')}")
    return result["data"]


def safe_call(api_name, params, fields, label):
    try:
        data = call_tushare(api_name, params, fields)
        items = [dict(zip(data["fields"], item)) for item in data["items"]]
        return items, None
    except Exception as e:
        return [], f"{label}: {e}"


# ============================================================
# 数据查询
# ============================================================

def get_suspend(today):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    ws = ",".join(WATCHLIST)
    items, err = safe_call("suspend_d", {
        "ts_code": ws, "start_date": month_ago, "end_date": today,
    }, "ts_code,trade_date,suspend_timing,suspend_type", "停复牌")
    if err:
        return [], [], err

    latest = {}
    for item in items:
        code = item["ts_code"]
        if code not in latest or item["trade_date"] > latest[code]["trade_date"]:
            latest[code] = item

    now = [v for v in latest.values() if v["suspend_type"] == "S"]
    today_resume = [i for i in items if i["suspend_type"] == "R" and i["trade_date"] == today]
    return now, today_resume, None


def get_forecast(today):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    items, err = safe_call("forecast", {
        "ts_code": ",".join(WATCHLIST), "start_date": week_ago, "end_date": today,
    }, "ts_code,ann_date,type,p_change_min,p_change_max,net_profit_min,net_profit_max,summary,change_reason", "业绩预告")
    return items, err


def get_express(today):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    items, err = safe_call("express", {
        "ts_code": ",".join(WATCHLIST), "start_date": week_ago, "end_date": today,
    }, "ts_code,ann_date,revenue,n_income,yoy_net_profit,yoy_dedu_np,perf_summary", "业绩快报")
    return items, err

# ============================================================
# 格式化
# ============================================================

def format_briefing(suspend_now, resume_today, suspend_err, forecasts, forecast_err, expresses, express_err, today_str):
    lines = [f"## 📊 盘前简报 {today_str}", ""]

    # 停复牌
    lines.append("### 📌 停复牌")
    if suspend_err:
        lines.append(f"> ⚠️ {suspend_err}")
    elif suspend_now:
        for s in suspend_now:
            name = NAME_MAP.get(s["ts_code"], s["ts_code"])
            lines.append(f"> ⏸ {name}({s['ts_code']}) 停牌中")
    else:
        lines.append("> ✅ 自选股无停牌")
    if resume_today:
        for s in resume_today:
            name = NAME_MAP.get(s["ts_code"], s["ts_code"])
            lines.append(f"> ▶ {name}({s['ts_code']}) 今日复牌")
    lines.append("")

    # 业绩预告
    lines.append("### 📢 业绩预告(近7天)")
    if forecast_err:
        lines.append(f"> ⚠️ {forecast_err}")
    elif forecasts:
        for f in forecasts:
            name = NAME_MAP.get(f["ts_code"], f["ts_code"])
            emoji = FORECAST_LABEL.get(f.get("type", ""), "⚪")
            n_min = f.get("p_change_min", "?")
            n_max = f.get("p_change_max", "?")
            summary = (f.get("summary", ""))[:60]
            lines.append(f"> {emoji} {name} {f.get('type','?')} ({n_min}%~{n_max}%)")
            if summary:
                lines.append(f">   {summary}")
    else:
        lines.append("> ℹ️ 无新预告")
    lines.append("")

    # 业绩快报
    lines.append("### 📋 业绩快报(近7天)")
    if express_err:
        lines.append(f"> ⚠️ {express_err}")
    elif expresses:
        for e in expresses:
            name = NAME_MAP.get(e["ts_code"], e["ts_code"])
            yoy = e.get("yoy_net_profit", "?")
            d = "🟢" if yoy and str(yoy) != "?" and float(yoy) > 0 else "🔴"
            lines.append(f"> {d} {name} 净利润同比: {yoy}%")
    else:
        lines.append("> ℹ️ 无新快报")

    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M')} | 数据: Tushare Pro")
    return "\n".join(lines)


# ============================================================
# 推送
# ============================================================

def push(title, content):
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        result = subprocess.run([
            "curl", "-s", "-X", "POST", url,
            "--data-urlencode", f"title={title}",
            "--data-urlencode", f"desp={content}",
            "--connect-timeout", "10", "--max-time", "60",
        ], capture_output=True, text=True, timeout=70)
        data = json.loads(result.stdout)
        if data.get("code") == 0:
            print("推送成功")
        else:
            print(f"推送失败: {data}")
    except Exception as e:
        print(f"推送异常: {e}")


# ============================================================
# 主流程
# ============================================================

def main():
    if not TUSHARE_TOKEN:
        print("❌ 请设置 TUSHARE_TOKEN 环境变量")
        sys.exit(1)

    today = datetime.now().strftime("%Y%m%d")
    today_display = datetime.now().strftime("%m/%d")

    print(f"盘前简报 {today_display}")
    print(f"自选股: {len(WATCHLIST)} 只")

    suspend_now, resume_today, s_err = get_suspend(today)
    forecasts, f_err = get_forecast(today)
    expresses, e_err = get_express(today)

    content = format_briefing(suspend_now, resume_today, s_err, forecasts, f_err, expresses, e_err, today_display)
    print(content)
    print()

    push(f"📊 盘前简报 {today_display}", content)


if __name__ == "__main__":
    main()
