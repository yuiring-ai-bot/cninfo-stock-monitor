#!/usr/bin/env python3
"""
A股年报监控 - 每日摘要
检查监控股票的前一天新公告，汇总发送
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

from cninfo_resolver import resolve_stock_info

CACHE_DIR = "/tmp/cninfo_watch"
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_STOCK_CONFIG = os.path.join(PROJECT_ROOT, "config", "stocks.json")


def load_stocks(config_path=None):
    path = config_path or os.environ.get("CNINFO_STOCK_CONFIG") or DEFAULT_STOCK_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    stocks = config.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        raise ValueError(f"{path} must contain a non-empty 'stocks' list")

    normalized = []
    for index, stock in enumerate(stocks, start=1):
        code = str(stock.get("code", "")).strip()
        if not code:
            raise ValueError(f"{path} stocks[{index}] is missing code")
        name = str(stock.get("name", "")).strip()
        if not name:
            name = resolve_stock_info(code).get("name") or code
        normalized.append({"code": code, "name": name})
    return normalized

def fetch_cninfo(stock_code, category='', pageSize=20, pageNum=1):
    stock_info = resolve_stock_info(stock_code)
    stock_str = f"{stock_info['code']},{stock_info['org_id']}"

    params = {
        'stock': stock_str,
        'tabName': 'fulltext',
        'pageSize': pageSize,
        'pageNum': pageNum,
        'column': stock_info['column'],
        'plate': stock_info['plate_param']
    }
    if category:
        params['category'] = category

    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(API_URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/"
    })

    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        anns = result.get('announcements') or []
        return anns

def check_stock(stock):
    """检查单只股票的前一天公告"""
    code = stock['code']
    name = stock['name']

    # 获取昨天的时间范围
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_start = int(yesterday.replace(hour=0, minute=0, second=0).timestamp() * 1000)

    # 获取年报 + 业绩预告
    anns_annual = fetch_cninfo(code, category='category_ndbg_szsh')
    anns_forecast = fetch_cninfo(code, category='category_yjygjxz')

    # 合并
    all_anns = anns_annual + anns_forecast
    seen = set()
    unique = []
    for a in all_anns:
        if a['announcementId'] not in seen:
            seen.add(a['announcementId'])
            unique.append(a)

    # 筛选昨天的公告
    yesterday_anns = [
        a for a in unique
        if a['announcementTime'] >= yesterday_start
    ]
    yesterday_anns.sort(key=lambda x: x['announcementTime'], reverse=True)

    return {
        'code': code,
        'name': name,
        'anns': yesterday_anns
    }

def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    results = []
    for stock in load_stocks(config_path):
        result = check_stock(stock)
        results.append(result)

    # 汇总
    total_count = sum(len(r['anns']) for r in results)

    if total_count == 0:
        print(f"[SILENT] {yesterday} 无新公告")
    else:
        lines = [f"📊 A股年报监控 - 每日摘要 ({yesterday})"]
        lines.append(f"=" * 40)

        for r in results:
            if r['anns']:
                lines.append(f"\n🏢 {r['name']} ({r['code']})")
                lines.append(f"  发现 {len(r['anns'])} 条新公告:")
                for a in r['anns'][:5]:
                    dt = datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
                    title = a['announcementTitle'][:40] + '...' if len(a['announcementTitle']) > 40 else a['announcementTitle']
                    lines.append(f"  • [{dt}] {title}")

        lines.append(f"\n{'=' * 40}")
        lines.append(f"总计: {total_count} 条新公告")

        print('\n'.join(lines))

if __name__ == "__main__":
    main()
