#!/usr/bin/env python3
"""
Query local ChromaDB chunks and return source context for downstream RAG use.

This script only retrieves local context. It does not call a model.
"""
import argparse
import os

from cninfo_paths import DATA_DIR
from stock_config import load_stocks

DB_DIR = os.path.join(DATA_DIR, "chromadb")


def get_company_name(code):
    return {stock["code"]: stock["name"] for stock in load_stocks()}.get(code, code)


def search_chunks(query, stock_code=None, k=15):
    import chromadb

    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_collection("cninfo_chunks")

    where = {"stock_code": stock_code} if stock_code else None
    results = collection.query(query_texts=[query], n_results=k, where=where)

    hits = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if results.get("distances") else []

    for index, chunk_id in enumerate(ids):
        score = 1.0 - distances[index] if index < len(distances) else 1.0
        hits.append({
            "id": chunk_id,
            "text": documents[index],
            "metadata": metadatas[index],
            "score": score,
        })
    return hits


def rag_answer(question, stock_code=None, k=15):
    hits = search_chunks(question, stock_code, k=k)

    context_parts = []
    sources = []
    seen_sources = set()

    for index, hit in enumerate(hits, start=1):
        metadata = hit["metadata"]
        source_key = f"{metadata['stock_code']}|{metadata['title']}|{metadata['page_num']}"
        company = get_company_name(metadata["stock_code"])

        context_parts.append(
            f"[Source {index}] Company: {company} ({metadata['stock_code']})\n"
            f"Filing: {metadata['title']}\n"
            f"Date: {metadata['publish_date']}\n"
            f"Type: {metadata.get('type', '')}\n"
            f"Page: {metadata['page_num']}\n"
            f"Text:\n{hit['text']}\n"
        )

        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        sources.append({
            "company": company,
            "stock_code": metadata["stock_code"],
            "title": metadata["title"],
            "publish_date": metadata["publish_date"],
            "type": metadata.get("type", ""),
            "page_num": metadata["page_num"],
            "relevance": round(hit["score"], 4),
        })

    return {
        "question": question,
        "stock_code": stock_code,
        "context": "\n---\n".join(context_parts),
        "sources": sources,
        "total_sources": len(sources),
        "total_chunks_retrieved": len(hits),
    }


def answer_question_formatted(question, stock_code=None):
    result = rag_answer(question, stock_code, k=20)

    print("=" * 60)
    print(f"Question: {result['question']}")
    if stock_code:
        print(f"Stock: {stock_code}")
    print(
        f"Retrieved {result['total_sources']} source files "
        f"and {result['total_chunks_retrieved']} chunks"
    )
    print("=" * 60)

    print("\nContext preview:")
    print("=" * 60)
    context = result["context"]
    print(context[:2000] + ("..." if len(context) > 2000 else ""))

    print("\n\nSources:")
    print("=" * 60)
    for index, source in enumerate(result["sources"], start=1):
        print(f"\n  [{index}] {source['company']} ({source['stock_code']})")
        print(f"      Filing: {source['title']}")
        print(f"      Date: {source['publish_date']} | Type: {source['type']}")
        print(f"      Page: {source['page_num']} | Relevance: {source['relevance']:.4f}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Query local ChromaDB chunks for RAG context")
    parser.add_argument("question", help="question to search for")
    parser.add_argument("stock_code", nargs="?", help="optional stock code filter")
    args = parser.parse_args()
    answer_question_formatted(args.question, args.stock_code)


if __name__ == "__main__":
    main()
