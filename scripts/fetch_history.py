#!/usr/bin/env python3
"""
A股历史财报抓取 - 巨潮网 API
用法: python3 fetch_history.py [stock_code] [stock_name]
抓取近5年: 年报、半年报、季报
抓取近2年: 所有类型公告
"""
import urllib.request
import urllib.parse
import json
import datetime
import os
import sys

HISTORY_DIR = "/tmp/cninfo_watch/history"
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

# 分类列表
CATEGORIES = {
    '年报': 'category_ndbg_szsh',
    '半年报': 'category_bndbg_szsh',
    '季报': 'category_jdbg_szsh',
    '业绩预告': 'category_yjygjxz',
}

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

def get_exchange(stock_code):
    if stock_code.startswith(('6', '8')):
        return 'sse'
    else:
        return 'szse'

def build_org_id(stock_code):
    exchange = get_exchange(stock_code)
    if exchange == 'sse':
        return f"gssh0{stock_code}"
    else:
        return f"gssz0{stock_code}"

def fetch_announcements(stock_code, category='', pageSize=100, pageNum=1):
    """获取公告列表"""
    exchange = get_exchange(stock_code)
    org_id = build_org_id(stock_code)
    stock_str = f"{stock_code},{org_id}"
    
    params = {
        'stock': stock_str,
        'tabName': 'fulltext',
        'pageSize': pageSize,
        'pageNum': pageNum,
        'column': exchange,
        'plate': 'sh' if exchange == 'sse' else 'sz'
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

def fetch_all_pages(stock_code, category='', max_pages=20):
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

def fetch_history(stock_code, stock_name):
    """抓取完整历史数据"""
    print(f"\n{'='*60}")
    print(f"📊 抓取 {stock_name} ({stock_code}) 历史数据")
    print(f"{'='*60}")
    
    stock_dir = os.path.join(HISTORY_DIR, stock_code)
    
    # 1. 近5年定期报告（年报、半年报、季报）
    print(f"\n📄 近5年定期报告:")
    report_types = [
        ('年报', 'category_ndbg_szsh', 5),
        ('半年报', 'category_bndbg_szsh', 5),
        ('季报', 'category_jdbg_szsh', 5),
        ('业绩预告', 'category_yjygjxz', 5),
    ]
    
    periodic_reports = []
    for name, cat, years in report_types:
        anns = fetch_all_pages(stock_code, category=cat)
        filtered = [a for a in anns if is_within_years(a['announcementTime'], years)]
        periodic_reports.extend(filtered)
        print(f"  {name}: 获取 {len(anns)} 条, 过滤后 {len(filtered)} 条")
    
    if periodic_reports:
        # 去重
        seen = set()
        unique = []
        for a in periodic_reports:
            if a['announcementId'] not in seen:
                seen.add(a['announcementId'])
                unique.append(a)
        unique.sort(key=lambda x: x['announcementTime'], reverse=True)
        
        data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'type': 'periodic_reports_5years',
            'fetch_time': datetime.datetime.now().isoformat(),
            'count': len(unique),
            'announcements': unique
        }
        save_report(data, os.path.join(stock_dir, 'periodic_reports_5years.json'))
    
    # 2. 近2年所有公告
    print(f"\n📋 近2年所有公告:")
    all_anns = []
    
    # 批量抓取（分多次请求）
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
    seen = set()
    unique = []
    for a in all_anns:
        if a['announcementId'] not in seen:
            seen.add(a['announcementId'])
            unique.append(a)
    
    filtered = [a for a in unique if is_within_years(a['announcementTime'], 2)]
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
    
    # 3. 生成索引摘要
    print(f"\n📑 生成索引摘要...")
    index = {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'fetch_time': datetime.datetime.now().isoformat(),
        'files': {
            'periodic_reports_5years': os.path.join(stock_dir, 'periodic_reports_5years.json'),
            'all_announcements_2years': os.path.join(stock_dir, 'all_announcements_2years.json'),
        },
        'summary': {
            'periodic_reports_count': len([a for a in filtered if 'category_ndbg_szsh' in str(a.get('announcementId', ''))]),
            'all_announcements_count': len(filtered),
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
