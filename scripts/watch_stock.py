#!/usr/bin/env python3
"""
cninfo A股年报财报监控脚本
用法: python watch_stock.py [stock_code] [stock_name]
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

def fetch_announcements(category, page_size=50, page_num=1):
    """抓取全市场指定类别公告"""
    data = urllib.parse.urlencode({
        'category': category,
        'pageSize': page_size,
        'pageNum': page_num
    }).encode()

    req = urllib.request.Request(API_URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/"
    })

    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        return result.get('announcements') or []

def watch_stock(stock_code, stock_name):
    """监控指定股票的新年报/业绩预告"""
    state_file = STATE_FILE(stock_code)

    # 读取上次检查状态
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
        last_time = state.get('last_announcement_time', 0)
    else:
        last_time = 0

    # 抓取年报 + 业绩预告
    categories = ['category_ndbg_szsh', 'category_yjygjxz']
    all_anns = []
    for cat in categories:
        anns = fetch_announcements(cat)
        filtered = [a for a in anns if a.get('secCode') == stock_code]
        all_anns.extend(filtered)

    # 去重 + 排序
    seen = set()
    unique = []
    for a in all_anns:
        if a['announcementId'] not in seen:
            seen.add(a['announcementId'])
            unique.append(a)
    unique.sort(key=lambda x: x['announcementTime'], reverse=True)

    # 找出新增
    new_anns = [a for a in unique if a['announcementTime'] > last_time]

    # 更新状态
    now_time = unique[0]['announcementTime'] if unique else last_time
    state = {
        'last_announcement_time': now_time,
        'last_check_time': int(datetime.datetime.now().timestamp() * 1000),
        'total_tracked': len(unique),
        'stock_code': stock_code,
        'stock_name': stock_name
    }
    with open(state_file, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # 输出结果
    if new_anns:
        print(f"🆕 {stock_name} ({stock_code}) 发现 {len(new_anns)} 条新公告:")
        for a in new_anns:
            ts = a['announcementTime'] // 1000
            dt = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            print(f"  [{dt}] {a['announcementTitle']}")
        return True, new_anns
    else:
        # 无新公告，静默退出，不输出任何内容
        return False, []

def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "600089"
    stock_name = sys.argv[2] if len(sys.argv) > 2 else "特变电工"
    has_new, anns = watch_stock(stock_code, stock_name)
    sys.exit(0 if has_new else 0)  # 总是成功，用于cron记录

if __name__ == "__main__":
    main()