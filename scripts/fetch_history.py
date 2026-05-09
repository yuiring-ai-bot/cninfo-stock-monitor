#!/usr/bin/env python3
"""
A股历史财报抓取 - 巨潮网 API
用法: python3 fetch_history.py [stock_code] [stock_name]
抓取全部历史: 年报
抓取近5年: 半年报、季报、业绩预告
抓取近2年: 所有类型公告
"""
import urllib.request
import urllib.parse
import json
import datetime
import os
import sys

from cninfo_paths import HISTORY_DIR
from cninfo_resolver import resolve_stock_info

API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

# 所有分类列表（用于近2年全量公告抓取）
ALL_CATEGORIES = [
    'category_ndbg_szsh',     # 年报
    'category_bndbg_szsh',    # 半年报
    'category_jdbg_szsh',     # 季报
    'category_yjygjxz',       # 业绩预告
    'category_yjpxgjztss',    # 业绩快报
    'category_gddh',          # 股东大会
    'category_rzrq',          # 融资融券
    'category_kjdb',          # 会计数据
    'category_gzwj',          # 规章制度
    'category_zjpc',          # 征集投票
    'category_zqdb',          # 证券质押
    'category_xgpx',          # 限售股解禁
    'category_dybmxz',        # 定向增发
    'category_szqy',          # 上市券商
    'category_zgfx',          # 整改函
    'category_qtfw',          # 其他法务
    'category_gszl',          # 公司章程
    'category_tzzgx',         # 投资者关系
]

def fetch_announcements(stock_code, category='', pageSize=100, pageNum=1):
    """获取公告列表"""
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

    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        anns = result.get('announcements') or []
        total = result.get('totalAnnouncement', 0)
        return anns, total

def fetch_all_pages(stock_code, category='', max_pages=50):
    """分页抓取所有公告"""
    all_anns = []
    page = 1
    while page <= max_pages:
        anns, total = fetch_announcements(stock_code, category, pageSize=100, pageNum=page)
        if not anns:
            break
        all_anns.extend(anns)
        if len(all_anns) >= total or len(anns) < 100:
            break
        page += 1
    return all_anns

def is_within_years(timestamp_ms, years):
    """检查公告时间是否在近N年内"""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=365*years)).timestamp() * 1000
    return timestamp_ms >= cutoff

def save_report(data, filepath):
    """保存报告JSON"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 保存: {filepath}")

def deduplicate(anns):
    """去重"""
    seen = set()
    unique = []
    for a in anns:
        if a['announcementId'] not in seen:
            seen.add(a['announcementId'])
            unique.append(a)
    return unique

def fetch_history(stock_code, stock_name):
    """抓取完整历史数据"""
    print(f"\n{'='*60}")
    print(f"📊 抓取 {stock_name} ({stock_code}) 历史数据")
    print(f"{'='*60}")

    stock_dir = os.path.join(HISTORY_DIR, stock_code)

    # ========== 1. 年报：全部历史（不设时间限制）==========
    print(f"\n📄 年报（全部历史）:")
    annual_reports = fetch_all_pages(stock_code, category='category_ndbg_szsh', max_pages=50)
    annual_reports = deduplicate(annual_reports)
    annual_reports.sort(key=lambda x: x['announcementTime'], reverse=True)
    print(f"  共获取 {len(annual_reports)} 条年报")

    if annual_reports:
        earliest = datetime.datetime.fromtimestamp(annual_reports[-1]['announcementTime']/1000).strftime('%Y-%m-%d')
        latest = datetime.datetime.fromtimestamp(annual_reports[0]['announcementTime']/1000).strftime('%Y-%m-%d')
        print(f"  时间范围: {earliest} ~ {latest}")

        data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'type': 'annual_reports_all_history',
            'fetch_time': datetime.datetime.now().isoformat(),
            'count': len(annual_reports),
            'earliest_date': earliest,
            'latest_date': latest,
            'announcements': annual_reports
        }
        save_report(data, os.path.join(stock_dir, 'annual_reports_all_history.json'))

    # ========== 2. 近5年半年报 ==========
    print(f"\n📄 近5年半年报:")
    half_reports = fetch_all_pages(stock_code, category='category_bndbg_szsh', max_pages=30)
    half_reports = [a for a in half_reports if is_within_years(a['announcementTime'], 5)]
    half_reports = deduplicate(half_reports)
    half_reports.sort(key=lambda x: x['announcementTime'], reverse=True)
    print(f"  近5年半年报: {len(half_reports)} 条")

    if half_reports:
        data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'type': 'half_reports_5years',
            'fetch_time': datetime.datetime.now().isoformat(),
            'count': len(half_reports),
            'announcements': half_reports
        }
        save_report(data, os.path.join(stock_dir, 'half_reports_5years.json'))

    # ========== 3. 近5年季报 ==========
    print(f"\n📄 近5年季报:")
    quarter_reports = fetch_all_pages(stock_code, category='category_jdbg_szsh', max_pages=30)
    quarter_reports = [a for a in quarter_reports if is_within_years(a['announcementTime'], 5)]
    quarter_reports = deduplicate(quarter_reports)
    quarter_reports.sort(key=lambda x: x['announcementTime'], reverse=True)
    print(f"  近5年季报: {len(quarter_reports)} 条")

    if quarter_reports:
        data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'type': 'quarter_reports_5years',
            'fetch_time': datetime.datetime.now().isoformat(),
            'count': len(quarter_reports),
            'announcements': quarter_reports
        }
        save_report(data, os.path.join(stock_dir, 'quarter_reports_5years.json'))

    # ========== 4. 近5年业绩预告 ==========
    print(f"\n📄 近5年业绩预告:")
    forecast_reports = fetch_all_pages(stock_code, category='category_yjygjxz', max_pages=30)
    forecast_reports = [a for a in forecast_reports if is_within_years(a['announcementTime'], 5)]
    forecast_reports = deduplicate(forecast_reports)
    forecast_reports.sort(key=lambda x: x['announcementTime'], reverse=True)
    print(f"  近5年业绩预告: {len(forecast_reports)} 条")

    if forecast_reports:
        data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'type': 'forecast_reports_5years',
            'fetch_time': datetime.datetime.now().isoformat(),
            'count': len(forecast_reports),
            'announcements': forecast_reports
        }
        save_report(data, os.path.join(stock_dir, 'forecast_reports_5years.json'))

    # ========== 5. 近2年所有公告 ==========
    print(f"\n📋 近2年所有公告:")
    all_anns = []

    for i in range(0, len(ALL_CATEGORIES), 3):
        cats = ALL_CATEGORIES[i:i+3]
        for cat in cats:
            try:
                anns = fetch_all_pages(stock_code, category=cat)
                all_anns.extend(anns)
                print(f"  {cat}: {len(anns)} 条")
            except Exception as e:
                print(f"  {cat}: 错误 - {e}")

    # 去重和过滤2年内
    all_anns = deduplicate(all_anns)
    filtered = [a for a in all_anns if is_within_years(a['announcementTime'], 2)]
    filtered.sort(key=lambda x: x['announcementTime'], reverse=True)

    data = {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'type': 'all_announcements_2years',
        'fetch_time': datetime.datetime.now().isoformat(),
        'count': len(filtered),
        'announcements': filtered
    }
    save_report(data, os.path.join(stock_dir, 'all_announcements_2years.json'))

    # ========== 6. 生成索引摘要 ==========
    print(f"\n📑 生成索引摘要...")

    index = {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'fetch_time': datetime.datetime.now().isoformat(),
        'files': {
            'annual_reports_all_history': 'annual_reports_all_history.json',
            'half_reports_5years': 'half_reports_5years.json',
            'quarter_reports_5years': 'quarter_reports_5years.json',
            'forecast_reports_5years': 'forecast_reports_5years.json',
            'all_announcements_2years': 'all_announcements_2years.json',
        },
        'summary': {
            'annual_reports_all_time': len(annual_reports),
            'annual_date_range': f"{earliest} ~ {latest}" if annual_reports else "N/A",
            'half_reports_5years': len(half_reports),
            'quarter_reports_5years': len(quarter_reports),
            'forecast_reports_5years': len(forecast_reports),
            'all_announcements_2years': len(filtered),
        }
    }
    save_report(index, os.path.join(stock_dir, 'index.json'))

    print(f"\n✅ {stock_name} 历史数据抓取完成!")
    print(f"   数据目录: {stock_dir}")
    return stock_dir

def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "600089"
    stock_name = sys.argv[2] if len(sys.argv) > 2 else "特变电工"
    fetch_history(stock_code, stock_name)

if __name__ == "__main__":
    main()
