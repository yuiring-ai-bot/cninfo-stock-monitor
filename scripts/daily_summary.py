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

CACHE_DIR = "/tmp/cninfo_watch"
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

# 监控列表
STOCKS = [
    {"code": "600089", "name": "特变电工"},
    {"code": "600927", "name": "永安期货"},
    {"code": "600824", "name": "益民集团"},
    {"code": "601186", "name": "中国铁建"},
]

def get_exchange(stock_code):
    if stock_code.startswith(('6', '8')):
        return 'sse'
    else:
        return 'szse'

def build_org_id(stock_code):
    """构建 orgId:
    - 上交所: gssh0 + 6位代码 (例: gssh0600089)
    - 深交所: gssz0 + 6位代码 (例: gssz0000001)
    
    ⚠️ 部分股票不在标准格式中（如永安期货gfbj0833840、中国铁建9900004347）
    优先从已知映射表查找，未知则通过 cninfo 搜索 API 反查。
    """
    # 已知非标准 orgId 映射（已通过 cninfo 搜索 API 验证）
    KNOWN_NONSTANDARD = {
        "600927": "gfbj0833840",   # 永安期货
        "601186": "9900004347",    # 中国铁建
    }
    if stock_code in KNOWN_NONSTANDARD:
        return KNOWN_NONSTANDARD[stock_code]
    
    exchange = get_exchange(stock_code)
    if exchange == 'sse':
        return f"gssh0{stock_code}"
    else:
        return f"gssz0{stock_code}"

def fetch_cninfo(stock_code, category='', pageSize=20, pageNum=1):
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
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    
    results = []
    for stock in STOCKS:
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