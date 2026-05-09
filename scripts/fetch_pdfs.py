#!/usr/bin/env python3
"""
PDF downloader wrapper for cninfo history outputs.

Usage:
  python scripts/fetch_pdfs.py 600089 annual_report --limit 5
  python scripts/fetch_pdfs.py 600089 all --limit 10
  python scripts/fetch_pdfs.py all annual_report
"""
import argparse
import json
import os
from datetime import datetime

from cninfo_pdfs import OUT_DIR, download_for_stock
from stock_config import load_stocks


def save_results(stock_code, filing_type, results):
    out_dir = os.path.join(OUT_DIR, "_runs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{stock_code}_{filing_type}_downloads.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "stock_code": stock_code,
            "filing_type": filing_type,
            "downloaded_at": datetime.now().isoformat(),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="巨潮网 PDF 批量下载器")
    parser.add_argument("stock_code", nargs="?", default="600089", help="股票代码，或 all")
    parser.add_argument(
        "filing_type",
        nargs="?",
        default="annual_report",
        help="类型: annual_report/semi_annual_report/quarterly_report/earnings_forecast/temporary_announcement/all",
    )
    parser.add_argument("--limit", "-n", type=int, default=0, help="限制数量（0=全部）")
    parser.add_argument("--config", help="股票配置文件，默认读取 config/stocks.json")
    args = parser.parse_args()

    if args.stock_code == "all":
        for stock in load_stocks(args.config):
            results = download_for_stock(stock["code"], args.filing_type, args.limit)
            if results:
                save_results(stock["code"], args.filing_type, results)
        return

    results = download_for_stock(args.stock_code, args.filing_type, args.limit)
    if results:
        save_results(args.stock_code, args.filing_type, results)


if __name__ == "__main__":
    main()
