#!/usr/bin/env python3
"""
Poll cninfo announcements without invoking any model.

This script is intended for high-frequency schedules. It only fetches cninfo
metadata, updates local state, and writes a JSON result. Downstream model or
analysis jobs should consume that JSON separately.
"""
import argparse
import datetime
import json
import os

from cninfo_paths import DATA_DIR
from stock_config import load_stocks
from watch_stock_cninfo import build_org_id, fetch_cninfo, get_exchange

DEFAULT_OUTPUT = os.path.join(DATA_DIR, "poll", "latest_announcements.json")
POLL_CATEGORIES = {
    "annual_report": "category_ndbg_szsh",
    "earnings_forecast": "category_yjygjxz",
}


def state_file(stock_code):
    return os.path.join(DATA_DIR, "state", f"{stock_code}_last_check.json")


def load_state(stock_code):
    path = state_file(stock_code)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(stock_code, state):
    path = state_file(stock_code)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def deduplicate(announcements):
    seen = set()
    unique = []
    for ann in announcements:
        ann_id = ann.get("announcementId")
        if ann_id in seen:
            continue
        seen.add(ann_id)
        unique.append(ann)
    unique.sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
    return unique


def poll_stock(stock):
    code = stock["code"]
    name = stock["name"]
    previous = load_state(code)
    last_time = previous.get("last_announcement_time", 0)

    all_announcements = []
    totals = {}
    for label, category in POLL_CATEGORIES.items():
        anns, total = fetch_cninfo(code, category=category)
        totals[label] = total
        for ann in anns:
            ann = dict(ann)
            ann["poll_category"] = label
            all_announcements.append(ann)

    unique = deduplicate(all_announcements)
    new_announcements = [
        ann for ann in unique
        if ann.get("announcementTime", 0) > last_time
    ]
    newest_time = unique[0].get("announcementTime", last_time) if unique else last_time

    state = {
        "last_announcement_time": newest_time,
        "last_check_time": int(datetime.datetime.now().timestamp() * 1000),
        "total_tracked": len(unique),
        "stock_code": code,
        "stock_name": name,
        "exchange": get_exchange(code),
        "org_id": build_org_id(code),
        "totals": totals,
    }
    save_state(code, state)

    return {
        "stock_code": code,
        "stock_name": name,
        "has_new": bool(new_announcements),
        "new_count": len(new_announcements),
        "new_announcements": new_announcements,
        "totals": totals,
        "state": state,
    }


def write_output(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Poll cninfo announcements without model calls")
    parser.add_argument("--config", help="stock config path; defaults to config/stocks.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="JSON output path")
    args = parser.parse_args()

    results = [poll_stock(stock) for stock in load_stocks(args.config)]
    payload = {
        "generated_at": datetime.datetime.now().isoformat(),
        "has_new": any(item["has_new"] for item in results),
        "new_count": sum(item["new_count"] for item in results),
        "results": results,
    }
    write_output(args.output, payload)
    if not payload["has_new"]:
        print(f"[SILENT] no new announcements; output={args.output}")
        return

    print(json.dumps({
        "has_new": payload["has_new"],
        "new_count": payload["new_count"],
        "output": args.output,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
