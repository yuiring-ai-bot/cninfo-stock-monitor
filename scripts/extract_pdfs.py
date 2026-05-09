#!/usr/bin/env python3
"""
P2-2: PDF文本提取 — 解析全部PDF，保留页码+章节标题，写入JSON文本库
依赖: pymupdf
"""
import json
import os
import hashlib
import sys
from pathlib import Path
from datetime import datetime

DATA_DIR = os.environ.get("CNINFO_DATA_DIR", "/tmp/cninfo_watch")
FILING_INDEX = os.path.join(DATA_DIR, "filings", "filing_index.json")
TEXT_DIR = os.path.join(DATA_DIR, "texts")
CHUNK_DIR = os.path.join(DATA_DIR, "chunks")

os.makedirs(TEXT_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)

def extract_pdf_text(pdf_path: str) -> list:
    """提取PDF文本，返回 [{page_num, text, headings}]"""
    import fitz  # pymupdf
    pages = []
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if not text.strip():
            continue
        # 尝试识别章节标题（以 . 或：结尾、全大写、数字开头、或大标题样式）
        lines = text.split("\n")
        headings = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 启发式：短行（<80字）、可能为标题
            if len(stripped) < 80 and stripped.isupper() and len(stripped) > 2:
                headings.append(stripped)
            elif stripped.startswith("第") and len(stripped) < 50:
                headings.append(stripped)
        pages.append({
            "page_num": page_num + 1,
            "text": text,
            "headings": headings,
            "char_count": len(text)
        })
    doc.close()
    return pages

def extract_pdf_text_simple(pdf_path: str) -> list:
    """轻量版PDF提取"""
    import fitz
    pages = []
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if not text.strip():
            continue
        pages.append({
            "page_num": page_num + 1,
            "text": text,
            "char_count": len(text)
        })
    doc.close()
    return pages

def main():
    # 读取filing索引
    if not os.path.exists(FILING_INDEX):
        print(f"❌ filing_index.json not found at {FILING_INDEX}")
        sys.exit(1)
    
    with open(FILING_INDEX) as f:
        index = json.load(f)
    
    filings = index.get("filings", [])
    total = len(filings)
    print(f"📄 共 {total} 条公告")

    stats = {"extracted": 0, "skipped_no_file": 0, "errors": 0, "previously_done": 0}

    for i, filing in enumerate(filings):
        pdf_path = filing.get("local_file_path", "")
        filing_id = filing.get("filing_id", "unknown")
        stock_code = filing.get("stock_code", "unknown")
        title = filing.get("announcement_title", "")[:40]

        # 检查是否已提取
        text_path = os.path.join(TEXT_DIR, f"{filing_id}.json")
        if os.path.exists(text_path):
            stats["previously_done"] += 1
            continue

        if not pdf_path or not os.path.exists(pdf_path):
            stats["skipped_no_file"] += 1
            print(f"  ⏭ [{i+1}/{total}] {stock_code}: PDF不存在: {pdf_path}")
            continue

        try:
            pages = extract_pdf_text_simple(pdf_path)
            if not pages:
                stats["skipped_no_file"] += 1
                continue

            total_chars = sum(p["char_count"] for p in pages)
            result = {
                "filing_id": filing_id,
                "stock_code": stock_code,
                "company_name": filing.get("company_name", ""),
                "announcement_title": filing.get("announcement_title", ""),
                "announcement_type": filing.get("announcement_type", ""),
                "publish_date": filing.get("publish_date", ""),
                "report_period": filing.get("report_period", ""),
                "total_pages": len(pages),
                "total_chars": total_chars,
                "pages": pages,
                "extracted_at": datetime.now().isoformat()
            }

            with open(text_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            stats["extracted"] += 1
            if (i+1) % 20 == 0:
                print(f"  ✅ [{i+1}/{total}] 已完成 {stats['extracted']} 个")

        except Exception as e:
            stats["errors"] += 1
            print(f"  ❌ [{i+1}/{total}] {stock_code}/{filing_id}: {e}")

    # 总报告
    print(f"\n{'='*50}")
    print(f"📊 PDF提取报告")
    print(f"  总公告数:       {total}")
    print(f"  本次新提取:     {stats['extracted']}")
    print(f"  之前已完成:     {stats['previously_done']}")
    print(f"  文件不存在:     {stats['skipped_no_file']}")
    print(f"  错误:           {stats['errors']}")
    
    # 更新 filing_index parse_status
    if stats["extracted"] > 0:
        print(f"\n🔄 更新 filing_index.json parse_status...")
        for filing in filings:
            tid = filing.get("filing_id", "")
            tp = os.path.join(TEXT_DIR, f"{tid}.json")
            if os.path.exists(tp):
                filing["parse_status"] = "extracted"
        index["updated_at"] = datetime.now().isoformat()
        with open(FILING_INDEX, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"✅ 已更新")
    
    print(f"\n📂 文本文件目录: {TEXT_DIR}")

if __name__ == "__main__":
    main()
