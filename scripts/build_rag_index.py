#!/usr/bin/env python3
"""
P2-3: 文本切分 + 向量索引构建 (ChromaDB内置embedding)
使用ChromaDB默认的all-MiniLM-L6-v2 (ONNX) - 分阶段构建避免超时
"""
import json
import os
import sys
import re
import gc
from datetime import datetime

from cninfo_paths import DATA_DIR

TEXT_DIR = os.path.join(DATA_DIR, "texts")
CHUNK_DIR = os.path.join(DATA_DIR, "chunks")
DB_DIR = os.path.join(DATA_DIR, "chromadb")
CHECKPOINT_FILE = os.path.join(CHUNK_DIR, "build_checkpoint.json")

MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP = 100

def ensure_dirs():
    os.makedirs(CHUNK_DIR, exist_ok=True)
    os.makedirs(DB_DIR, exist_ok=True)

def chunk_page_text(text: str, page_num: int, max_chars: int = MAX_CHUNK_CHARS):
    """将单页文本按段落+长度切分为chunk，返回(page_num, text)列表"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            nl = text.rfind("\n\n", start, end)
            if nl > start + max_chars // 2:
                end = nl + 2
            else:
                sent = text.rfind("。", start, end)
                if sent > start + max_chars // 2:
                    end = sent + 1
                else:
                    sent = text.rfind(". ", start, end)
                    if sent > start + max_chars // 2:
                        end = sent + 2
        chunk_text = text[start:end].strip()
        if chunk_text and len(chunk_text) > 20:
            chunks.append((page_num, chunk_text))
        start = end - CHUNK_OVERLAP if end < len(text) else len(text)
    return chunks

def load_checkpoint():
    """从checkpoint恢复构建状态"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}

def save_checkpoint(state):
    """保存checkpoint"""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)

def build_index():
    print("=" * 50)
    print("📦 P2-3: 文本切分 + 向量索引构建")
    print("=" * 50)
    
    ensure_dirs()
    
    # 加载checkpoint
    cp = load_checkpoint()
    processed_files = set(cp.get("processed_files", []))
    
    # 导入ChromaDB（延迟导入，先完成chunk生成）
    import chromadb
    client = chromadb.PersistentClient(path=DB_DIR)
    
    # 检查是否已有collection（checkpoint恢复时不删除）
    try:
        collection = client.get_collection("cninfo_chunks")
        existing_count = collection.count()
        print(f"🔄 发现已有ChromaDB索引 ({existing_count:,} chunks)，增量构建")
    except Exception:
        # 无collection，创建新的
        collection = client.create_collection(
            name="cninfo_chunks",
            metadata={"hnsw:space": "cosine"})
        print("🆕 创建新的ChromaDB索引")
        existing_count = 0
    
    # 如果从checkpoint恢复，避免重复添加已嵌入的filing
    BATCH = 100
    total_embedded = cp.get("total_embedded", 0) or existing_count
    
    text_files = sorted([
        fn for fn in os.listdir(TEXT_DIR)
        if fn.endswith(".json")
    ])
    
    print(f"📂 找到 {len(text_files)} 个文本文件")
    
    # 如果之前已完成一部分，恢复进度
    if processed_files:
        print(f"🔄 已处理 {len(processed_files)} 个文件，从中断处继续")
    
    for fn in text_files:
        fid = fn.replace(".json", "")
        
        # 跳过已处理的文件
        if fid in processed_files:
            print(f"  ⏭️ 跳过已处理: {fn}")
            continue
        
        # 读取文本文件
        tpath = os.path.join(TEXT_DIR, fn)
        with open(tpath) as f:
            data = json.load(f)
        
        pages = data.get("pages", data.get("text", {}))
        stock_code = data.get("stock_code", "?")
        title = data.get("announcement_title", "公告")
        pub_date = data.get("publish_date", "")
        ftype = data.get("announcement_type", "")
        source_url = data.get("source_url", "")
        
        # 切分chunk
        raw_chunks = []
        if isinstance(pages, dict):
            for page_num_str, page_text in pages.items():
                raw_chunks.extend(chunk_page_text(page_text, int(page_num_str)))
        elif isinstance(pages, list):
            for page in pages:
                page_text = page.get("text", "")
                page_num = page.get("page_num", 1)
                raw_chunks.extend(chunk_page_text(page_text, int(page_num)))
        
        if not raw_chunks:
            processed_files.add(fid)
            save_checkpoint({"processed_files": list(processed_files), "total_embedded": total_embedded})
            print(f"  ⚠️ 无chunk: {fn}")
            continue
        
        # 构建chunk数据
        chunk_ids = []
        chunk_texts = []
        chunk_metadatas = []
        
        for idx, (page_num, chunk_text) in enumerate(raw_chunks):
            chunk_ids.append(f"{fid}_p{page_num}_c{idx}")
            chunk_texts.append(chunk_text)
            chunk_metadatas.append({
                "filing_id": fid,
                "stock_code": stock_code,
                "page_num": page_num,
                "title": title[:200],
                "publish_date": pub_date,
                "type": ftype,
                "char_count": len(chunk_text)
            })
        
        # 分批embedding并写入
        for i in range(0, len(chunk_ids), BATCH):
            batch_end = min(i + BATCH, len(chunk_ids))
            collection.add(
                documents=chunk_texts[i:batch_end],
                metadatas=chunk_metadatas[i:batch_end],
                ids=chunk_ids[i:batch_end]
            )
            total_embedded += batch_end - i
            print(f"  📤 {fid}: 向量化 {total_embedded}", end="", flush=True)
            # 回车覆盖上一行
            print("\r", end="", flush=True)
        
        # 标记已完成
        processed_files.add(fid)
        save_checkpoint({"processed_files": list(processed_files), "total_embedded": total_embedded})
        print(f"  ✅ {fn} → {len(chunk_ids)} chunks (累计 {total_embedded})")
        
        # 显式GC
        del data, pages, raw_chunks, chunk_ids, chunk_texts, chunk_metadatas
        gc.collect()
    
    # 保存最终chunk元数据
    chunk_index = {
        "total_chunks": total_embedded,
        "num_files": len(processed_files),
        "generated_at": datetime.now().isoformat(),
    }
    chunk_index_path = os.path.join(CHUNK_DIR, "chunk_index.json")
    with open(chunk_index_path, "w", encoding="utf-8") as f:
        json.dump(chunk_index, f, ensure_ascii=False, indent=2)
    
    # 清理checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
    
    print(f"\n✅ 向量索引构建完成！")
    print(f"  📊 Chunk总量: {collection.count()}")
    print(f"  📂 文件数: {len(processed_files)}")
    print(f"  💾 数据库路径: {DB_DIR}")

if __name__ == "__main__":
    build_index()
