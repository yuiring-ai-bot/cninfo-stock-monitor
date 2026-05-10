#!/usr/bin/env python3
"""
P2-4: RAG问答接口 — 基于ChromaDB向量索引，返回来源文件+页码
"""
import json
import os
import sys

from cninfo_paths import DATA_DIR
from stock_config import load_stocks

DB_DIR = os.path.join(DATA_DIR, "chromadb")

def get_company_name(code):
    """根据股票代码获取公司名"""
    return {stock["code"]: stock["name"] for stock in load_stocks()}.get(code, code)

def search_chunks(query: str, stock_code: str = None, k: int = 15) -> list:
    """检索相似chunk"""
    import chromadb
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_collection("cninfo_chunks")
    
    where = None
    if stock_code:
        where = {"stock_code": stock_code}
    
    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=where
    )
    
    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1.0 - results["distances"][0][i] if results.get("distances") else 1.0
        })
    
    return hits

def rag_answer(question: str, stock_code: str = None, k: int = 15) -> dict:
    """
    RAG问答：检索相关chunk，返回上下文供LLM回答
    返回：{question, context, source_chunks}
    """
    hits = search_chunks(question, stock_code, k=k)
    
    context_parts = []
    sources = []
    seen_sources = set()
    
    for i, h in enumerate(hits):
        meta = h["metadata"]
        source_key = f"{meta['stock_code']}|{meta['title']}|{meta['page_num']}"
        
        context_parts.append(
            f"[来源{i+1}] 公司: {get_company_name(meta['stock_code'])} ({meta['stock_code']})\n"
            f"公告: {meta['title']}\n"
            f"日期: {meta['publish_date']}\n"
            f"类型: {meta.get('type', '')}\n"
            f"页码: {meta['page_num']}\n"
            f"原文:\n{h['text']}\n"
        )
        
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append({
                "company": get_company_name(meta['stock_code']),
                "stock_code": meta['stock_code'],
                "title": meta['title'],
                "publish_date": meta['publish_date'],
                "type": meta.get('type', ''),
                "page_num": meta['page_num'],
                "relevance": round(h['score'], 4)
            })
    
    context = "\n---\n".join(context_parts)
    
    return {
        "question": question,
        "stock_code": stock_code,
        "context": context,
        "sources": sources,
        "total_sources": len(sources),
        "total_chunks_retrieved": len(hits)
    }

def answer_question_formatted(question: str, stock_code: str = None):
    """格式化输出RAG结果"""
    result = rag_answer(question, stock_code, k=20)
    
    print(f"{'='*60}")
    print(f"🔍 问题: {result['question']}")
    if stock_code:
        print(f"📌 股票: {stock_code}")
    print(f"📎 检索到 {result['total_sources']} 个来源文件, {result['total_chunks_retrieved']} 个chunk")
    print(f"{'='*60}")
    
    print(f"\n📋 上下文摘要（用于LLM回答）:")
    print(f"{'='*60}")
    print(result['context'][:2000] + ("..." if len(result['context']) > 2000 else ""))
    
    print(f"\n\n📂 来源文件列表:")
    print(f"{'='*60}")
    for i, s in enumerate(result['sources']):
        print(f"\n  [{i+1}] {s['company']} ({s['stock_code']})")
        print(f"      公告: {s['title']}")
        print(f"      日期: {s['publish_date']} | 类型: {s['type']}")
        print(f"      页码: {s['page_num']} | 相关度: {s['relevance']:.4f}")
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 rag_query.py <查询问题> [股票代码]")
        print("示例: python3 rag_query.py '主要风险有哪些' 600089")
        sys.exit(1)
    
    question = sys.argv[1]
    stock = sys.argv[2] if len(sys.argv) > 2 else None
    answer_question_formatted(question, stock)
