#!/usr/bin/env python3
"""
cninfo 新股票录入 — 抓取完整历史年报/季报/半年报/公告
用法: python onboard_stock.py [stock_code] [stock_name]
"""
import urllib.request
import urllib.parse
import json
import datetime
import os
import sys

API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
DEFAULT_STOCK_CODE = "600089"
DEFAULT_STOCK_NAME = "特变电工"  # 示例股票，可通过命令行参数替换
OUTPUT_DIR = lambda code: f"/tmp/cninfo_watch/{code}_history"
os.makedirs(OUTPUT_DIR(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STOCK_CODE), exist_ok=True)

CATEGORIES = {
    'annual': 'category_ndbg_szsh',      # 年度报告
    'semi': 'category_bndbg_szsh',        # 半年度报告
    'quarterly': 'category_jjdbg_szsh',   # 季度报告
    'forecast': 'category_yjygjxz',       # 业绩预告/快报
}

def fetch_all_pages(category, stock_code, max_pages=50):
    """分页抓取所有公告"""
    all_anns = []
    for page in range(1, max_pages + 1):
        data = urllib.parse.urlencode({
            'category': category,
            'pageSize': 50,
            'pageNum': page
        }).encode()

        req = urllib.request.Request(API_URL, data=data, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Referer": "http://www.cninfo.com.cn/"
        })

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                anns = result.get('announcements') or []
                if not anns:
                    break
                filtered = [a for a in anns if a.get('secCode') == stock_code]
                if not filtered:
                    break
                all_anns.extend(filtered)
                print(f"  page {page}: +{len(filtered)}条 [{stock_code}]")
        except Exception as e:
            print(f"  page {page} 错误: {e}")
            break
    return all_anns

def filter_by_date(anns, days_back):
    """按日期过滤"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days_back)
    cutoff_ms = int(cutoff.timestamp() * 1000)
    return [a for a in anns if a['announcementTime'] >= cutoff_ms]

def onboard_stock(stock_code, stock_name):
    """录入新股票：抓取完整历史"""
    print(f"\n{'='*60}")
    print(f"录入新股票: {stock_name} ({stock_code})")
    print(f"{'='*60}\n")

    out_dir = OUTPUT_DIR(stock_code)
    os.makedirs(out_dir, exist_ok=True)

    results = {}

    # 1. 全部历史年报
    print(f"[1/4] 抓取全部历史年报...")
    annual = fetch_all_pages(CATEGORIES['annual'], stock_code)
    results['annual'] = annual
    print(f"  共 {len(annual)} 条年报\n")

    # 2. 近5年半年报
    print(f"[2/4] 抓取近5年半年报...")
    semi = fetch_all_pages(CATEGORIES['semi'], stock_code)
    semi_5y = filter_by_date(semi, 365 * 5)
    results['semi_5y'] = semi_5y
    print(f"  共 {len(semi)} 条，5年内 {len(semi_5y)} 条\n")

    # 3. 近5年季报
    print(f"[3/4] 抓取近5年季度报告...")
    quarterly = fetch_all_pages(CATEGORIES['quarterly'], stock_code)
    quarterly_5y = filter_by_date(quarterly, 365 * 5)
    results['quarterly_5y'] = quarterly_5y
    print(f"  共 {len(quarterly)} 条，5年内 {len(quarterly_5y)} 条\n")

    # 4. 近2年所有类型公告
    print(f"[4/4] 抓取近2年全部公告...")
    all_types = []
    for cat_name, cat_code in CATEGORIES.items():
        anns = fetch_all_pages(cat_code, stock_code)
        all_types.extend(anns)
    # 去重
    seen = set()
    unique_all = []
    for a in all_types:
        if a['announcementId'] not in seen:
            seen.add(a['announcementId'])
            unique_all.append(a)
    all_2y = filter_by_date(unique_all, 365 * 2)
    results['all_2y'] = all_2y
    print(f"  去重后共 {len(unique_all)} 条，2年内 {len(all_2y)} 条\n")

    # 保存
    for key, anns in results.items():
        out_file = os.path.join(out_dir, f"{key}.json")
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(anns, f, ensure_ascii=False, indent=2)
        print(f"  已保存: {out_file}")

    # 生成摘要
    summary = {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'onboard_time': datetime.datetime.now().isoformat(),
        'total_annual': len(annual),
        'total_semi_5y': len(semi_5y),
        'total_quarterly_5y': len(quarterly_5y),
        'total_all_2y': len(all_2y),
        'annual_years': sorted(set(
            datetime.datetime.fromtimestamp(a['announcementTime']/1000).year
            for a in annual
        ))
    }

    summary_file = os.path.join(out_dir, "_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"录入完成: {stock_name}")
    print(f"  全部年报: {len(annual)} 条")
    print(f"  近5年半年报: {len(semi_5y)} 条")
    print(f"  近5年季报: {len(quarterly_5y)} 条")
    print(f"  近2年所有公告: {len(all_2y)} 条")
    print(f"  年报覆盖年份: {summary['annual_years']}")
    print(f"{'='*60}")

    return results

def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STOCK_CODE
    stock_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STOCK_NAME
    onboard_stock(stock_code, stock_name)

if __name__ == "__main__":
    main()
