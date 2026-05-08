#!/usr/bin/env python3
"""
cninfo A-share announcement monitor.
Usage: python scripts/watch_stock.py [stock_code] [stock_name]
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


def fetch_announcements(category, page_size=50, page_num=1):
    """Fetch announcements for a market-wide cninfo category."""
    data = urllib.parse.urlencode({
        "category": category,
        "pageSize": page_size,
        "pageNum": page_num,
    }).encode()

    req = urllib.request.Request(API_URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/",
    })

    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("announcements") or []


def watch_stock(stock_code, stock_name):
    """Watch one stock for new annual reports and performance forecasts."""
    state_file = STATE_FILE(stock_code)

    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        last_time = state.get("last_announcement_time", 0)
    else:
        last_time = 0

    categories = ["category_ndbg_szsh", "category_yjygjxz"]
    all_anns = []
    for cat in categories:
        anns = fetch_announcements(cat)
        filtered = [a for a in anns if a.get("secCode") == stock_code]
        all_anns.extend(filtered)

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
    state = {
        "last_announcement_time": now_time,
        "last_check_time": int(datetime.datetime.now().timestamp() * 1000),
        "total_tracked": len(unique),
        "stock_code": stock_code,
        "stock_name": stock_name,
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if new_anns:
        print(f"[NEW] {stock_name} ({stock_code}) found {len(new_anns)} new announcements:")
        for announcement in new_anns:
            ts = announcement["announcementTime"] // 1000
            dt = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            print(f"  [{dt}] {announcement['announcementTitle']}")
        return True, new_anns

    return False, []


def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STOCK_CODE
    stock_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STOCK_NAME
    has_new, _ = watch_stock(stock_code, stock_name)
    sys.exit(0 if has_new else 0)


if __name__ == "__main__":
    main()
