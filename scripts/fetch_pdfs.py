#!/usr/bin/env python3
"""
PDF 下载器 - 从巨潮网批量下载公告 PDF
用法:
  python3 scripts/fetch_pdfs.py [stock_code] [type] [--limit N]
  python3 scripts/fetch_pdfs.py 600089 annual_report --limit 5
  python3 scripts/fetch_pdfs.py 600089 all --limit 10
"""

import json, os, sys, time, hashlib, urllib.request, urllib.error, argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# === 配置 ===
OUT_DIR = "/tmp/cninfo_watch/pdfs"
MAX_WORKERS = 4
CHUNK_SIZE = 65536

os.makedirs(OUT_DIR, exist_ok=True)


def build_pdf_url(announcement_id: str) -> str:
    """构建巨潮网 PDF 下载 URL"""
    return (
        f"http://www.cninfo.com.cn/new/announcement/download"
        f"?announcementId={announcement_id}"
        f"&timestamp={int(time.time() * 1000)}"
    )


def download_pdf(url: str, timeout: int = 30) -> tuple[bytes, str]:
    """下载 PDF，返回 (content, error)"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://www.cninfo.com.cn/",
            "Accept": "application/pdf,*/*",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read()
            if len(content) < 1024:
                return b"", "File too small"
            return content, ""
    except urllib.error.HTTPError as e:
        return b"", f"HTTP {e.code}"
    except Exception as e:
        return b"", str(e)[:60]


def compute_hash(data: bytes) -> str:
    """计算 SHA256 hash"""
    return hashlib.sha256(data).hexdigest()


def save_filing(code: str, ann: dict, content: bytes, status: str, error: str) -> dict:
    """保存 PDF 到本地，更新元数据"""
    filing_id = ann.get("announcementId") or ann.get("filing_id", "")
    local_dir = f"{OUT_DIR}/{code}"
    os.makedirs(local_dir, exist_ok=True)

    result = {
        "announcementId": filing_id,
        "stock_code": code,
        "announcement_title": ann.get("announcementTitle", ""),
        "publish_date": ann.get("publish_date", ""),
        "announcement_type": ann.get("announcement_type", ""),
        "download_status": status,
        "error": error,
        "local_file_path": "",
        "file_hash": "",
        "file_size_bytes": 0,
    }

    if status == "success" and content:
        filename = f"{filing_id}.pdf"
        path = f"{local_dir}/{filename}"
        with open(path, "wb") as f:
            f.write(content)
        result["local_file_path"] = path
        result["file_hash"] = compute_hash(content)
        result["file_size_bytes"] = len(content)

    return result


def fetch_pdfs_for_stock(code: str, filing_type: str = "all", limit: int = 0) -> list[dict]:
    """
    下载某只股票指定类型的 PDF
    
    Args:
        code: 股票代码
        filing_type: annual_report / semi_annual_report / quarterly_report / 
                     earnings_forecast / temporary_announcement / all
        limit: 限制数量（0=全部）
    
    Returns:
        下载结果列表
    """
    idx_path = f"/tmp/cninfo_watch/filings/{code}_filings.json"
    if not os.path.exists(idx_path):
        print(f"❌ 找不到 {idx_path}，请先运行 fetch_history.py")
        return []

    with open(idx_path) as f:
        data = json.load(f)

    filings = data["filings"]
    
    # 过滤类型
    if filing_type != "all":
        filings = [f for f in filings if f["announcement_type"] == filing_type]
    
    # 限制数量
    if limit > 0:
        filings = filings[:limit]

    print(f"📥 [{code}] {data['company_name']} - {len(filings)} 份 {filing_type} 待下载")
    
    results = []
    done = 0
    success = 0
    
    for ann in filings:
        filing_id = ann.get("announcementId") or ann.get("filing_id", "")
        
        # 检查是否已下载
        pdf_path = f"{OUT_DIR}/{code}/{filing_id}.pdf"
        if os.path.exists(pdf_path):
            # 已存在，跳过但记录
            results.append({
                "announcementId": filing_id,
                "stock_code": code,
                "announcement_title": ann.get("announcement_title", ""),
                "publish_date": ann.get("publish_date", ""),
                "download_status": "already_exists",
                "local_file_path": pdf_path,
                "file_hash": compute_hash(open(pdf_path, "rb").read()),
                "file_size_bytes": os.path.getsize(pdf_path),
                "error": "",
            })
            success += 1
            done += 1
            print(f"\r  进度: {done}/{len(filings)} (已有: {success})", end="", flush=True)
            continue
        
        # 下载
        url = build_pdf_url(filing_id)
        content, err = download_pdf(url)
        
        status = "success" if not err and len(content) > 1024 else "failed"
        result = save_filing(code, ann, content, status, err)
        results.append(result)
        
        done += 1
        if status == "success":
            success += 1
        
        print(f"\r  进度: {done}/{len(filings)} (成功: {success})", end="", flush=True)
        
        # 礼貌限速
        if done < len(filings):
            time.sleep(0.5)
    
    print()  # 换行
    return results


def main():
    parser = argparse.ArgumentParser(description="巨潮网 PDF 批量下载器")
    parser.add_argument("stock_code", nargs="?", default="600089", help="股票代码")
    parser.add_argument("filing_type", nargs="?", default="annual_report", 
                        help="类型: annual_report/semi_annual_report/quarterly_report/earnings_forecast/temporary_announcement/all")
    parser.add_argument("--limit", "-n", type=int, default=0, help="限制数量（0=全部）")
    parser.add_argument("--workers", "-w", type=int, default=4, help="并发数")
    
    args = parser.parse_args()
    
    global MAX_WORKERS
    MAX_WORKERS = args.workers

    results = fetch_pdfs_for_stock(args.stock_code, args.filing_type, args.limit)
    
    if not results:
        return
    
    # 统计
    success = sum(1 for r in results if r["download_status"] == "success")
    already = sum(1 for r in results if r["download_status"] == "already_exists")
    failed = len(results) - success - already
    
    print(f"\n📊 下载结果:")
    print(f"  ✅ 成功: {success}")
    print(f"  ⏭️  已存在: {already}")
    print(f"  ❌ 失败: {failed}")
    
    # 保存下载结果
    out_path = f"/tmp/cninfo_watch/filings/{args.stock_code}_{args.filing_type}_downloads.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "stock_code": args.stock_code,
            "filing_type": args.filing_type,
            "downloaded_at": datetime.now().isoformat(),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"💾 结果已保存: {out_path}")


if __name__ == "__main__":
    main()