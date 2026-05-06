#!/usr/bin/env python3
"""
A股个股公告监控 - 东方财富 API 版本
用法: python watch_stock_em.py [stock_code] [stock_name]
"""
import urllib.request
import json
import datetime
import os
import sys

CACHE_DIR = "/tmp/cninfo_watch"
BASE_URL = "http://np-anotice-stock.eastmoney.com/api/security/ann"
os.makedirs(CACHE_DIR, exist_ok=True)

STATE_FILE = lambda code: os.path.join(CACHE_DIR, f"{code}_last_check_em.json")

def fetch_page(stock_code, page=1, page_size=50):
    """获取单页公告"""
    url = f"{BASE_URL}?sr=-1&page_size={page_size}&page_index={page}&ann_type=A&stock_list={stock_code}&client_source=web"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://data.eastmoney.com/"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    return result.get('data', {}).get('list', [])

def watch_stock(stock_code, stock_name, page_size=50):
    """
    监控指定股票的新公告
    返回: (has_new, new_anns, all_current)
    """
    state_file = STATE_FILE(stock_code)

    # 读取上次检查状态
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
        last_notice_date = state.get('last_notice_date', '')
        last_title = state.get('last_title', '')
        print(f"[{stock_name}] 上次检查: {last_notice_date} - {last_title[:40]}")
    else:
        last_notice_date = ''
        last_title = ''
        print(f"[{stock_name}] 首次检查")

    # 获取最新一页（最新公告）
    current_anns = fetch_page(stock_code, page=1, page_size=page_size)

    if not current_anns:
        print(f"  API 返回空")
        return False, [], []

    # 最新公告
    latest = current_anns[0]
    latest_date = latest.get('notice_date', '')[:10]
    latest_title = latest.get('title', '')

    # 检查是否有新公告
    has_new = (latest_date > last_notice_date) or (last_notice_date == '')

    new_anns = []
    if has_new:
        # 找出所有新公告（从第一页中找时间 > last_notice_date 的）
        for a in current_anns:
            if a.get('notice_date', '')[:10] > last_notice_date:
                new_anns.append(a)
            else:
                break  # 已按时间排序，后面都更旧

    # 更新状态
    state = {
        'last_notice_date': latest_date,
        'last_title': latest_title,
        'last_check_time': datetime.datetime.now().isoformat(),
        'stock_code': stock_code,
        'stock_name': stock_name
    }
    with open(state_file, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if new_anns:
        print(f"\n{'='*60}")
        print(f"🆕 {stock_name} ({stock_code}) 发现 {len(new_anns)} 条新公告:")
        for a in new_anns[:10]:
            notice_date = a.get('notice_date', '')[:10]
            title = a.get('title', '')
            cols = a.get('columns', [])
            col_name = cols[0].get('column_name', '') if cols else ''
            print(f"  [{notice_date}] [{col_name}]")
            print(f"    {title[:60]}")
        print(f"{'='*60}")
        return True, new_anns, current_anns
    else:
        print(f"  ✅ 无新公告")
        return False, [], current_anns

def get_all_history(stock_code, max_pages=30):
    """获取完整历史公告（分页）"""
    all_anns = []
    for page in range(1, max_pages + 1):
        anns = fetch_page(stock_code, page=page)
        if not anns:
            break
        all_anns.extend(anns)
        if page <= 3 or page % 5 == 0:
            dates = anns[-1].get('notice_date', '')[:10], anns[0].get('notice_date', '')[:10]
            print(f"  page {page}: +{len(anns)}条 ({dates[0]} ~ {dates[1]})")
    return all_anns

def main():
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "600089"
    stock_name = sys.argv[2] if len(sys.argv) > 2 else "特变电工"

    if len(sys.argv) > 3 and sys.argv[3] == '--onboard':
        # 录入模式：获取完整历史
        print(f"\n{'='*60}")
        print(f"录入新股票: {stock_name} ({stock_code})")
        print(f"{'='*60}\n")
        all_anns = get_all_history(stock_code)
        print(f"\n共获取 {len(all_anns)} 条公告")
        return

    # 默认：监控模式
    has_new, new_anns, _ = watch_stock(stock_code, stock_name)
    sys.exit(0)

if __name__ == "__main__":
    main()