#!/usr/bin/env python3
"""
A股年报财报监控 - 巨潮网 API 版本
用法: python3 scripts/watch_stock_cninfo.py [stock_code] [stock_name]
"""
import urllib.request
import urllib.parse
import json
import datetime
import os
import sys

CACHE_DIR = "/tmp/cninfo_watch"
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
STATE_FILE = lambda code: os.path.join(CACHE_DIR, f"{code}_last_check.json")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_exchange(stock_code):
    """根据股票代码判断交易所: 上交所(6/8开头) / 深交所(0/3开头)"""
    if stock_code.startswith(('6', '8')):
        return 'sse'
    else:
        return 'szse'

def build_org_id(stock_code):
    """构建 orgId:
    - 上交所: gssh0 + 6位代码 (例: gssh0600089)
    - 深交所: gssz0 + 6位代码 (例: gssz0000001)
    """
    exchange = get_exchange(stock_code)
    if exchange == 'sse':
        return f"gssh0{stock_code}"
    else:
        return f"gssz0{stock_code}"

def fetch_cninfo(stock_code, category='', pageSize=50, pageNum=1):
    """获取巨潮 API 数据"""
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
        total = result.get('totalAnnouncement', 0)
        return anns, total

def watch_stock(stock_code, stock_name):
    """监控指定股票的新年报/业绩预告"""
    state_file = STATE_FILE(stock_code)
    
    # 读取上次状态（静默）
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
        last_time = state.get('last_announcement_time', 0)
    else:
        last_time = 0
    
    # 获取年报 + 业绩预告
    anns_annual, total_annual = fetch_cninfo(stock_code, category='category_ndbg_szsh')
    anns_forecast, total_forecast = fetch_cninfo(stock_code, category='category_yjygjxz')
    
    # 合并去重（按 announcementId）
    all_anns = anns_annual + anns_forecast
    seen = set()
    unique = []
    for a in all_anns:
        if a['announcementId'] not in seen:
            seen.add(a['announcementId'])
            unique.append(a)
    unique.sort(key=lambda x: x['announcementTime'], reverse=True)
    
    # 找出新公告（时间大于上次记录）
    new_anns = [a for a in unique if a['announcementTime'] > last_time]
    
    # 更新状态
    now_time = unique[0]['announcementTime'] if unique else last_time
    exchange = get_exchange(stock_code)
    state = {
        'last_announcement_time': now_time,
        'last_check_time': int(datetime.datetime.now().timestamp() * 1000),
        'total_tracked': len(unique),
        'stock_code': stock_code,
        'stock_name': stock_name,
        'exchange': exchange,
        'org_id': build_org_id(stock_code)
    }
    with open(state_file, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # 只在新公告时输出
    if new_anns:
        print(f"🆕 {stock_name} ({stock_code}) 发现 {len(new_anns)} 条新公告:")
        for a in new_anns[:10]:
            dt = datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
            print(f"  [{dt}] {a['announcementTitle']}")
        return True, new_anns
    else:
        # 无新公告，静默退出，不输出任何内容
        return False, []

def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "600089"
    stock_name = sys.argv[2] if len(sys.argv) > 2 else "特变电工"
    has_new, _ = watch_stock(stock_code, stock_name)
    sys.exit(0)

if __name__ == "__main__":
    main()