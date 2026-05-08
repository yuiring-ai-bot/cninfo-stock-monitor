#!/usr/bin/env python3
"""
A-share financial report monitor using the cninfo API.
Usage: python scripts/watch_stock_cninfo.py [stock_code] [stock_name]
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

CACHE_DIR = "/tmp/cninfo_watch"
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
DEFAULT_STOCK_CODE = "600089"
DEFAULT_STOCK_NAME = "特变电工"  # Example stock; override with CLI arguments.
STATE_FILE = lambda code: os.path.join(CACHE_DIR, f"{code}_last_check.json")

os.makedirs(CACHE_DIR, exist_ok=True)

KNOWN_NONSTANDARD_ORG_IDS = {
    "600927": "gfbj0833840",  # 永安期货
    "601186": "9900004347",   # 中国铁建
}


def get_exchange(stock_code):
    """Infer exchange from the stock code prefix."""
    if stock_code.startswith(("6", "8")):
        return "sse"
    return "szse"


def build_org_id(stock_code):
    """Build cninfo orgId, with overrides for known non-standard stock mappings."""
    if stock_code in KNOWN_NONSTANDARD_ORG_IDS:
        return KNOWN_NONSTANDARD_ORG_IDS[stock_code]

    exchange = get_exchange(stock_code)
    if exchange == "sse":
        return f"gssh0{stock_code}"
    return f"gssz0{stock_code}"


def fetch_cninfo(stock_code, category="", page_size=50, page_num=1):
    """Fetch cninfo announcements for one stock."""
    exchange = get_exchange(stock_code)
    org_id = build_org_id(stock_code)
    stock_str = f"{stock_code},{org_id}"

    params = {
        "stock": stock_str,
        "tabName": "fulltext",
        "pageSize": page_size,
        "pageNum": page_num,
        "column": exchange,
        "plate": "sh" if exchange == "sse" else "sz",
    }
    if category:
        params["category"] = category

    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(API_URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/",
    })

    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        anns = result.get("announcements") or []
        total = result.get("totalAnnouncement", 0)
        return anns, total


def watch_stock(stock_code, stock_name):
    """Watch one stock for new annual reports and performance forecasts."""
    state_file = STATE_FILE(stock_code)

    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        last_time = state.get("last_announcement_time", 0)
    else:
        last_time = 0

    anns_annual, total_annual = fetch_cninfo(stock_code, category="category_ndbg_szsh")
    anns_forecast, total_forecast = fetch_cninfo(stock_code, category="category_yjygjxz")

    all_anns = anns_annual + anns_forecast
    seen = set()
    unique = []
    for announcement in all_anns:
        announcement_id = announcement["announcementId"]
        if announcement_id not in seen:
            seen.add(announcement_id)
            unique.append(announcement)
    unique.sort(key=lambda x: x["announcementTime"], reverse=True)

    new_anns = [a for a in unique if a["announcementTime"] > last_time]

    now_time = unique[0]["announcementTime"] if unique else last_time
    exchange = get_exchange(stock_code)
    state = {
        "last_announcement_time": now_time,
        "last_check_time": int(datetime.datetime.now().timestamp() * 1000),
        "total_tracked": len(unique),
        "stock_code": stock_code,
        "stock_name": stock_name,
        "exchange": exchange,
        "org_id": build_org_id(stock_code),
        "total_annual": total_annual,
        "total_forecast": total_forecast,
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if new_anns:
        print(f"[NEW] {stock_name} ({stock_code}) found {len(new_anns)} new announcements:")
        for announcement in new_anns[:10]:
            dt = datetime.datetime.fromtimestamp(
                announcement["announcementTime"] / 1000
            ).strftime("%Y-%m-%d")
            print(f"  [{dt}] {announcement['announcementTitle']}")
        return True, new_anns

    return False, []


def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STOCK_CODE
    stock_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STOCK_NAME
    watch_stock(stock_code, stock_name)
    sys.exit(0)


if __name__ == "__main__":
    main()
