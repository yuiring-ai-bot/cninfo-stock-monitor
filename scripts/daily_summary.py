#!/usr/bin/env python3
"""
Daily summary for configured stocks.

This script only fetches cninfo metadata and prints a text summary. It does not
call any model.
"""
import argparse
import datetime
import json
import urllib.parse
import urllib.request

from cninfo_resolver import resolve_stock_info
from stock_config import load_stocks

API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"


def fetch_cninfo(stock_code, category="", page_size=20, page_num=1):
    stock_info = resolve_stock_info(stock_code)
    stock_str = f"{stock_info['code']},{stock_info['org_id']}"

    params = {
        "stock": stock_str,
        "tabName": "fulltext",
        "pageSize": page_size,
        "pageNum": page_num,
        "column": stock_info["column"],
        "plate": stock_info["plate_param"],
    }
    if category:
        params["category"] = category

    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(data=data, url=API_URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/",
    })

    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("announcements") or []


def check_stock(stock, since_ms):
    code = stock["code"]
    name = stock["name"]

    anns_annual = fetch_cninfo(code, category="category_ndbg_szsh")
    anns_forecast = fetch_cninfo(code, category="category_yjygjxz")

    seen = set()
    unique = []
    for announcement in anns_annual + anns_forecast:
        announcement_id = announcement.get("announcementId")
        if announcement_id in seen:
            continue
        seen.add(announcement_id)
        unique.append(announcement)

    new_announcements = [
        item for item in unique
        if item.get("announcementTime", 0) >= since_ms
    ]
    new_announcements.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)

    return {"code": code, "name": name, "anns": new_announcements}


def main():
    parser = argparse.ArgumentParser(description="Print daily cninfo summary for configured stocks")
    parser.add_argument("--config", help="stock config path; defaults to config/stocks.json")
    parser.add_argument("--days", type=int, default=1, help="look back this many days")
    args = parser.parse_args()

    target_day = datetime.datetime.now() - datetime.timedelta(days=args.days)
    since = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
    since_ms = int(since.timestamp() * 1000)
    since_label = since.strftime("%Y-%m-%d")

    results = [check_stock(stock, since_ms) for stock in load_stocks(args.config)]
    total_count = sum(len(result["anns"]) for result in results)

    if total_count == 0:
        print(f"[SILENT] no new announcements since {since_label}")
        return

    lines = [f"A-share filing summary since {since_label}", "=" * 40]
    for result in results:
        if not result["anns"]:
            continue
        lines.append(f"\n{result['name']} ({result['code']})")
        lines.append(f"  found {len(result['anns'])} new announcements:")
        for announcement in result["anns"][:5]:
            dt = datetime.datetime.fromtimestamp(
                announcement["announcementTime"] / 1000
            ).strftime("%Y-%m-%d")
            title = announcement.get("announcementTitle", "")
            if len(title) > 60:
                title = title[:60] + "..."
            lines.append(f"  - [{dt}] {title}")

    lines.append(f"\nTotal: {total_count} new announcements")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
