#!/usr/bin/env python3
"""
Market-category cninfo monitor for one configured stock.

This legacy monitor fetches market-wide category pages and filters locally.
Prefer watch_stock_cninfo.py for stock-specific cninfo queries.
"""
import argparse
import datetime
import json
import os
import urllib.parse
import urllib.request

from cninfo_paths import DATA_DIR
from cninfo_resolver import resolve_stock_info
from stock_config import load_stocks

API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
STATE_DIR = os.path.join(DATA_DIR, "state")
os.makedirs(STATE_DIR, exist_ok=True)


def state_file(code):
    return os.path.join(STATE_DIR, f"{code}_last_check_market.json")


def resolve_cli_stock(code=None, name=None, config_path=None):
    if code:
        if name:
            return code, name
        info = resolve_stock_info(code)
        return code, info.get("name") or code
    first = load_stocks(config_path)[0]
    return first["code"], first["name"]


def fetch_announcements(category, page_size=50, page_num=1):
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
    path = state_file(stock_code)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        last_time = state.get("last_announcement_time", 0)
    else:
        last_time = 0

    all_announcements = []
    for category in ("category_ndbg_szsh", "category_yjygjxz"):
        all_announcements.extend([
            item for item in fetch_announcements(category)
            if item.get("secCode") == stock_code
        ])

    seen = set()
    unique = []
    for announcement in all_announcements:
        announcement_id = announcement.get("announcementId")
        if announcement_id in seen:
            continue
        seen.add(announcement_id)
        unique.append(announcement)
    unique.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)

    new_announcements = [
        item for item in unique
        if item.get("announcementTime", 0) > last_time
    ]

    newest_time = unique[0].get("announcementTime", last_time) if unique else last_time
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "last_announcement_time": newest_time,
            "last_check_time": int(datetime.datetime.now().timestamp() * 1000),
            "total_tracked": len(unique),
            "stock_code": stock_code,
            "stock_name": stock_name,
        }, f, ensure_ascii=False, indent=2)

    if new_announcements:
        print(f"[NEW] {stock_name} ({stock_code}) found {len(new_announcements)} new announcements:")
        for announcement in new_announcements:
            dt = datetime.datetime.fromtimestamp(
                announcement["announcementTime"] / 1000
            ).strftime("%Y-%m-%d")
            print(f"  [{dt}] {announcement.get('announcementTitle', '')}")
        return True, new_announcements

    print(f"[SILENT] {stock_name} ({stock_code}) no new announcements")
    return False, []


def main():
    parser = argparse.ArgumentParser(description="Watch one stock by filtering market-wide cninfo categories")
    parser.add_argument("stock_code", nargs="?", help="stock code; defaults to first configured stock")
    parser.add_argument("stock_name", nargs="?", help="stock name; resolved when omitted")
    parser.add_argument("--config", help="stock config path")
    args = parser.parse_args()

    code, name = resolve_cli_stock(args.stock_code, args.stock_name, args.config)
    watch_stock(code, name)


if __name__ == "__main__":
    main()
