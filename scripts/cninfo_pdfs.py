#!/usr/bin/env python3
"""
巨潮网 PDF 下载器 (session + 多策略重试)
- 策略1: 直接附件 URL (http://www.cninfo.com.cn/new/{adjunctUrl})
- 策略2: 带 cookie 的 session 下载
- 策略3: POST announcement/download API
- 策略4: 带完整 Referer 的请求

用法:
  python3 scripts/cninfo_pdfs.py 601186 annual_report  # 下载年报
  python3 scripts/cninfo_pdfs.py 600927 all            # 下载全量
  python3 scripts/cninfo_pdfs.py all annual_report     # 全部股票年报
"""

import argparse
import json, os, time, hashlib, http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

from cninfo_resolver import resolve_stock_info
from cninfo_paths import FILINGS_DIR, HISTORY_DIR, PDF_DIR
from stock_config import load_stocks

# === 配置 ===
OUT_DIR = PDF_DIR
TIMEOUT = 12


def to_pdf_stock_info(stock_info: dict) -> dict:
    return {
        'code': stock_info['code'],
        'name': stock_info.get('name', stock_info['code']),
        'orgId': stock_info['org_id'],
        'column': stock_info['column'],
        'plate': stock_info['plate_param'],
    }


def build_session():
    """建立带 cookie 的 opener"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    ]
    return opener, cj


def try_refresh_session(opener, cj):
    """刷新 session，获取新 cookie"""
    try:
        opener.open('http://www.cninfo.com.cn/', timeout=8)
    except Exception:
        pass


def download_pdf(ann: dict, stock_info: dict, opener=None) -> tuple[bytes, str, str]:
    """
    多策略下载 PDF
    
    Returns: (content, strategy_used, error)
    """
    if opener is None:
        opener, _ = build_session()

    ann_id = ann.get('announcementId') or ann.get('filing_id', '')
    org_id = stock_info.get('orgId', '')
    plate = stock_info.get('plate', 'sh')
    stock_code = stock_info.get('code', '')
    adj_url = ann.get('adjunctUrl', '')

    if not adj_url:
        return b'', '', 'no adjunctUrl'

    # cninfo PDF files are served from static.cninfo.com.cn; www often returns 500.
    static_url = f'http://static.cninfo.com.cn/{adj_url}'
    www_url = f'http://www.cninfo.com.cn/new/{adj_url}'

    strategies = [
        {
            'url': static_url,
            'method': 'GET',
            'headers': {
                'Referer': 'http://www.cninfo.com.cn/',
                'Accept': 'application/pdf,*/*',
            }
        },
        {
            'url': static_url,
            'method': 'GET',
            'headers': {
                'Referer': f'http://www.cninfo.com.cn/new/disclosure/stock?plateId={plate}&orgId={org_id}&announcementId={ann_id}',
                'Accept': 'application/pdf,*/*',
            }
        },
        {
            'url': www_url,
            'method': 'GET',
            'headers': {
                'Referer': f'http://www.cninfo.com.cn/new/disclosure/stock?plateId={plate}&orgId={org_id}&announcementId={ann_id}',
                'Accept': 'application/pdf,*/*',
            },
            'refresh_session': True,
        },
        {
            'url': 'http://www.cninfo.com.cn/new/announcement/download',
            'method': 'POST',
            'data': urllib.parse.urlencode({
                'announcementId': ann_id,
                'timestamp': int(time.time() * 1000),
            }).encode(),
            'headers': {
                'Referer': f'http://www.cninfo.com.cn/new/disclosure/stock?plateId={plate}&orgId={org_id}&announcementId={ann_id}',
                'Accept': 'application/pdf,*/*',
            }
        },
    ]

    for i, strat in enumerate(strategies):
        try:
            refresh = strat.pop('refresh_session', False)
            if refresh:
                try_refresh_session(opener, None)

            headers = {**strat.get('headers', {})}
            req = urllib.request.Request(strat['url'], data=strat.get('data'), headers=headers)

            with opener.open(req, timeout=TIMEOUT) as r:
                content = r.read()

            if len(content) < 1024:
                continue  # 文件太小，跳过
            if b'%PDF' not in content[:5]:
                continue

            return content, f'strategy_{i+1}', ''

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b'', f'strategy_{i+1}', '404'
            continue
        except Exception as e:
            err = str(e)[:50]
            continue

    return b'', 'all_failed', f'HTTP 500 or timeout for all strategies'


def _load_filings_from_history(code: str, target_type: str) -> list[dict]:
    """从 history JSON 加载公告，映射类型"""
    TYPE_MAP = {
        'annual_reports_all_history': 'annual_report',
        'half_reports_5years': 'semi_annual_report',
        'quarter_reports_5years': 'quarterly_report',
        'all_announcements_2years': 'temporary_announcement',
        'forecast_reports_5years': 'earnings_forecast',
    }
    filings = []
    for fname, ftype in TYPE_MAP.items():
        if target_type != 'all' and ftype != target_type:
            continue
        fpath = f'{HISTORY_DIR}/{code}/{fname}.json'
        if os.path.exists(fpath):
            with open(fpath) as f:
                d = json.load(f)
            for ann in (d.get('announcements') or []):
                ann = dict(ann)  # copy
                ann['announcement_type'] = ftype
                ann['category'] = fname
                filings.append(ann)
    return filings


def download_for_stock(code: str, target_type: str = 'all', limit: int = 0) -> list[dict]:
    """下载某股票指定类型的 PDF"""
    stock_info = to_pdf_stock_info(resolve_stock_info(code))
    print(f'  {stock_info["name"]} ({code}) - orgId={stock_info["orgId"]}')

    filings = _load_filings_from_history(code, target_type)
    if limit > 0:
        filings = filings[:limit]
    if not filings:
        print(f'  无 {target_type} 类型公告')
        return []
    print(f'  共 {len(filings)} 份待处理')

    opener, cj = build_session()
    try_refresh_session(opener, cj)

    results = []
    done = ok = skip = fail = 0
    for ann in filings:
        ann_id = ann.get('announcementId') or ''
        pdf_path = f'{OUT_DIR}/{code}/{ann_id}.pdf'
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        # 已下载则跳过
        if os.path.exists(pdf_path):
            results.append({'announcementId': ann_id,
                            'title': ann.get('announcementTitle', ''),
                            'status': 'already_exists', 'path': pdf_path})
            skip += 1
            done += 1
            print(f'\r  进度 {done}/{len(filings)} 成功:{ok} 已有:{skip} 失败:{fail}', end='', flush=True)
            continue

        content, strategy, error = download_pdf(ann, stock_info, opener)
        is_pdf = b'%PDF' in content[:5] if content else False

        if content and len(content) > 1024:
            with open(pdf_path, 'wb') as f:
                f.write(content)
            sha256 = hashlib.sha256(content).hexdigest()
            results.append({'announcementId': ann_id,
                            'title': ann.get('announcementTitle', ''),
                            'status': 'success', 'size': len(content),
                            'is_pdf': is_pdf, 'strategy': strategy, 'path': pdf_path,
                            'file_hash': sha256})
            ok += 1
        else:
            results.append({'announcementId': ann_id,
                            'title': ann.get('announcementTitle', ''),
                            'status': 'failed', 'error': error})
            fail += 1

        done += 1
        print(f'\r  进度 {done}/{len(filings)} 成功:{ok} 已有:{skip} 失败:{fail}', end='', flush=True)
        if done < len(filings):
            time.sleep(0.3)
    print()
    _update_filing_index(code, results)
    return results


def _update_filing_index(code: str, results: list[dict]):
    result_map = {
        r['announcementId']: r
        for r in results
        if r.get('status') in ('success', 'already_exists') and r.get('announcementId')
    }
    if not result_map:
        return

    updated = 0
    paths = [
        os.path.join(FILINGS_DIR, f'{code}_filings.json'),
        os.path.join(FILINGS_DIR, 'filing_index.json'),
    ]
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for filing in data.get('filings', []):
            filing_id = str(filing.get('filing_id') or filing.get('announcementId', ''))
            if filing_id not in result_map:
                continue
            result = result_map[filing_id]
            filing['local_file_path'] = result.get('path', '')
            filing['file_hash'] = result.get('file_hash', '')
            filing['download_status'] = 'downloaded'
            filing['file_size_kb'] = result.get('size', 0) // 1024
            if filing.get('adjunctUrl'):
                filing['pdf_url'] = f"http://static.cninfo.com.cn/{filing['adjunctUrl']}"
            updated += 1
        data['generated_at'] = datetime.now().isoformat()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    if updated:
        print(f'  Updated {updated} filing metadata rows')


def main():
    parser = argparse.ArgumentParser(description="Download cninfo PDFs")
    parser.add_argument("stock_code", nargs="?", default="all", help="stock code, or all")
    parser.add_argument("target_type", nargs="?", default="annual_report", help="filing type, or all")
    parser.add_argument("limit", nargs="?", type=int, default=0, help="max PDFs per stock, 0 means no limit")
    parser.add_argument("--config", help="stock config path")
    args = parser.parse_args()

    stock_code = args.stock_code
    target_type = args.target_type
    limit = args.limit

    if stock_code == 'all':
        all_codes = [stock['code'] for stock in load_stocks(args.config)]
        print(f'全量下载: {all_codes}')
        for code in all_codes:
            results = download_for_stock(code, target_type, limit)
            time.sleep(1)
    else:
        results = download_for_stock(stock_code, target_type, limit)

        if results:
            out = os.path.join(FILINGS_DIR, f"{stock_code}_{target_type}_downloads.json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'w') as f:
                json.dump({'code': stock_code, 'type': target_type, 'downloaded_at': datetime.now().isoformat(), 'results': results}, f, ensure_ascii=False, indent=2)

            ok = sum(1 for r in results if r['status'] == 'success')
            skip = sum(1 for r in results if r['status'] == 'already_exists')
            fail = sum(1 for r in results if r['status'] == 'failed')
            print(f'\n📊 {stock_code}: 成功={ok}, 已有={skip}, 失败={fail}')


if __name__ == '__main__':
    main()
