#!/usr/bin/env python3
"""
Eastmoney announcement monitor for one configured stock.
"""
import argparse
import datetime
import json
import os
import urllib.request

from cninfo_paths import DATA_DIR
from cninfo_resolver import resolve_stock_info
from stock_config import load_stocks

BASE_URL = "http://np-anotice-stock.eastmoney.com/api/security/ann"
STATE_DIR = os.path.join(DATA_DIR, "state")
os.makedirs(STATE_DIR, exist_ok=True)


def state_file(code):
    return os.path.join(STATE_DIR, f"{code}_last_check_em.json")


def resolve_cli_stock(code=None, name=None, config_path=None):
    if code:
        if name:
            return code, name
        info = resolve_stock_info(code)
        return code, info.get("name") or code
    first = load_stocks(config_path)[0]
    return first["code"], first["name"]


def fetch_page(stock_code, page=1, page_size=50):
    url = (
        f"{BASE_URL}?sr=-1&page_size={page_size}&page_index={page}"
        f"&ann_type=A&stock_list={stock_code}&client_source=web"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://data.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result.get("data", {}).get("list", [])


def watch_stock(stock_code, stock_name, page_size=50):
    path = state_file(stock_code)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        last_notice_date = state.get("last_notice_date", "")
    else:
        last_notice_date = ""

    current_announcements = fetch_page(stock_code, page=1, page_size=page_size)
    if not current_announcements:
        print(f"[WARN] {stock_name} ({stock_code}) empty Eastmoney response")
        return False, [], []

    latest = current_announcements[0]
    latest_date = latest.get("notice_date", "")[:10]
    latest_title = latest.get("title", "")

    new_announcements = []
    if latest_date > last_notice_date or not last_notice_date:
        for announcement in current_announcements:
            if announcement.get("notice_date", "")[:10] > last_notice_date:
                new_announcements.append(announcement)
            else:
                break

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "last_notice_date": latest_date,
            "last_title": latest_title,
            "last_check_time": datetime.datetime.now().isoformat(),
            "stock_code": stock_code,
            "stock_name": stock_name,
        }, f, ensure_ascii=False, indent=2)

    if new_announcements:
        print(f"[NEW] {stock_name} ({stock_code}) found {len(new_announcements)} new announcements:")
        for announcement in new_announcements[:10]:
            notice_date = announcement.get("notice_date", "")[:10]
            title = announcement.get("title", "")
            columns = announcement.get("columns", [])
            column_name = columns[0].get("column_name", "") if columns else ""
            print(f"  [{notice_date}] [{column_name}] {title[:80]}")
        return True, new_announcements, current_announcements

    print(f"[SILENT] {stock_name} ({stock_code}) no new announcements")
    return False, [], current_announcements


def get_all_history(stock_code, max_pages=30):
    all_announcements = []
    for page in range(1, max_pages + 1):
        announcements = fetch_page(stock_code, page=page)
        if not announcements:
            break
        all_announcements.extend(announcements)
        if page <= 3 or page % 5 == 0:
            start = announcements[-1].get("notice_date", "")[:10]
            end = announcements[0].get("notice_date", "")[:10]
            print(f"  page {page}: +{len(announcements)} ({start} ~ {end})")
    return all_announcements


def main():
    parser = argparse.ArgumentParser(description="Watch one stock using Eastmoney")
    parser.add_argument("stock_code", nargs="?", help="stock code; defaults to first configured stock")
    parser.add_argument("stock_name", nargs="?", help="stock name; resolved when omitted")
    parser.add_argument("--config", help="stock config path")
    parser.add_argument("--onboard", action="store_true", help="fetch historical Eastmoney announcement pages")
    args = parser.parse_args()

    code, name = resolve_cli_stock(args.stock_code, args.stock_name, args.config)
    if args.onboard:
        announcements = get_all_history(code)
        print(f"fetched {len(announcements)} Eastmoney announcements for {name} ({code})")
        return

    watch_stock(code, name)


if __name__ == "__main__":
    main()
