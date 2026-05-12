#!/usr/bin/env python3
"""
Rule-based entity extraction for filings.

This script is incremental by default. It hashes each text JSON file and only
re-extracts entities for filings whose text changed or was not processed before.
Use --force to rebuild all extracted entities.
"""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime

from cninfo_paths import DATA_DIR
from neo4j_graph import NEO4J_PASS, NEO4J_URI, NEO4J_USER

TEXT_DIR = os.path.join(DATA_DIR, "texts")
ENTITIES_DIR = os.path.join(DATA_DIR, "entities")
ENTITIES_FILE = os.path.join(ENTITIES_DIR, "extracted_entities.json")
STATE_FILE = os.path.join(ENTITIES_DIR, "extract_state.json")
os.makedirs(ENTITIES_DIR, exist_ok=True)

METRIC_KEYWORDS = {
    "营业收入": "revenue",
    "净利润": "net_profit",
    "总资产": "total_assets",
    "净资产": "net_assets",
    "每股收益": "eps",
    "资产负债率": "debt_ratio",
    "毛利率": "gross_margin",
    "净资产收益率": "roe",
    "经营活动现金流": "operating_cashflow",
    "基本每股收益": "basic_eps",
}

EVENT_KEYWORDS = {
    "重大投资": ["投资", "出资", "设立", "新建", "扩建"],
    "项目投产": ["投产", "试运行", "竣工验收", "达产"],
    "并购重组": ["并购", "重组", "收购", "吸收合并", "资产置换"],
    "诉讼仲裁": ["诉讼", "仲裁", "起诉", "上诉", "判决"],
    "担保": ["担保", "保证", "抵押", "质押担保"],
    "减值": ["减值", "计提", "资产减值", "商誉减值"],
    "分红": ["分红", "利润分配", "派息", "现金分红"],
    "回购": ["回购", "股份回购", "注销股份"],
    "高管变动": ["辞职", "聘任", "免去", "董事长", "总经理", "董事会"],
    "股权质押": ["质押", "股权质押", "冻结"],
    "关联交易": ["关联交易", "关联方", "关联关系"],
    "重大合同": ["合同", "协议", "订单", "中标"],
    "业绩预告": ["业绩预告", "业绩快报", "业绩变动", "业绩预增"],
}

RISK_KEYWORDS = [
    "风险",
    "不确定性",
    "可能影响",
    "不利影响",
    "波动风险",
    "政策风险",
    "市场风险",
    "经营风险",
    "财务风险",
    "汇率风险",
    "原材料价格",
    "竞争加剧",
    "行业波动",
]


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def empty_entities():
    return {"risks": [], "events": [], "metrics": []}


def extract_entities_from_text(text, stock_code, filing_id, page_num, chunk_id):
    results = empty_entities()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for keyword, metric_type in METRIC_KEYWORDS.items():
        if keyword not in text:
            continue
        for line in lines:
            if keyword not in line:
                continue
            numbers = re.findall(r"[-]?\d+(?:,\d{3})*(?:\.\d+)?[%亿元万股]*", line)
            if not numbers:
                continue
            results["metrics"].append({
                "name": keyword,
                "type": metric_type,
                "value": numbers[0],
                "context": line[:160],
                "source_filing_id": filing_id,
                "source_page": page_num,
                "source_chunk_id": chunk_id,
                "stock_code": stock_code,
            })
            break

    for event_type, keywords in EVENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword not in text:
                continue
            for line in lines:
                if keyword in line and len(line) > 10:
                    results["events"].append({
                        "name": line[:80],
                        "type": event_type,
                        "description": line[:240],
                        "source_filing_id": filing_id,
                        "source_page": page_num,
                        "source_chunk_id": chunk_id,
                        "stock_code": stock_code,
                    })
                    break
            break

    for keyword in RISK_KEYWORDS:
        if keyword not in text:
            continue
        for line in lines:
            if keyword in line and len(line) > 15:
                results["risks"].append({
                    "name": line[:80],
                    "type": "risk",
                    "description": line[:240],
                    "confidence": "medium",
                    "source_filing_id": filing_id,
                    "source_page": page_num,
                    "source_chunk_id": chunk_id,
                    "stock_code": stock_code,
                })
                break

    return results


def dedup_entities(entities, key):
    seen = set()
    result = []
    for entity in entities:
        dedup_key = (
            entity.get("source_filing_id", ""),
            entity.get("stock_code", ""),
            str(entity.get(key, ""))[:120],
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        result.append(entity)
    return result


def remove_filing_entities(entities, filing_id):
    return {
        "risks": [item for item in entities.get("risks", []) if item.get("source_filing_id") != filing_id],
        "events": [item for item in entities.get("events", []) if item.get("source_filing_id") != filing_id],
        "metrics": [item for item in entities.get("metrics", []) if item.get("source_filing_id") != filing_id],
    }


def has_filing_entities(entities, filing_id):
    return any(
        item.get("source_filing_id") == filing_id
        for key in ("risks", "events", "metrics")
        for item in entities.get(key, [])
    )


def merge_entities(base, extracted):
    for key in ("risks", "events", "metrics"):
        base.setdefault(key, []).extend(extracted.get(key, []))
    return base


def process_text_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    filing_id = data.get("filing_id") or os.path.splitext(os.path.basename(path))[0]
    stock_code = data.get("stock_code", "unknown")
    extracted = empty_entities()

    pages = data.get("pages", [])
    if isinstance(pages, dict):
        pages = [{"page_num": page_num, "text": text} for page_num, text in pages.items()]

    for page in pages:
        page_num = int(page.get("page_num", 1))
        text = page.get("text", "")
        chunk_id = f"{filing_id}_chunk_{page_num}_0"
        page_entities = extract_entities_from_text(text, stock_code, filing_id, page_num, chunk_id)
        merge_entities(extracted, page_entities)

    return filing_id, stock_code, extracted


def process_all_stocks(force=False):
    if not os.path.exists(TEXT_DIR):
        raise FileNotFoundError(f"text directory not found: {TEXT_DIR}")

    state = load_json(STATE_FILE, {"files": {}})
    existing = load_json(ENTITIES_FILE, empty_entities())
    entities = empty_entities() if force else {
        "risks": existing.get("risks", []),
        "events": existing.get("events", []),
        "metrics": existing.get("metrics", []),
    }

    text_files = sorted(fn for fn in os.listdir(TEXT_DIR) if fn.endswith(".json"))
    stats = {"processed": 0, "skipped": 0, "errors": 0}
    print(f"Processing {len(text_files)} text files")

    for fname in text_files:
        path = os.path.join(TEXT_DIR, fname)
        filing_id = os.path.splitext(fname)[0]
        digest = file_sha256(path)
        previous = state.get("files", {}).get(filing_id, {})

        if (
            not force
            and previous.get("sha256") == digest
            and has_filing_entities(entities, filing_id)
        ):
            stats["skipped"] += 1
            continue

        try:
            actual_filing_id, stock_code, extracted = process_text_file(path)
            entities = remove_filing_entities(entities, actual_filing_id)
            merge_entities(entities, extracted)
            state.setdefault("files", {})[actual_filing_id] = {
                "sha256": digest,
                "stock_code": stock_code,
                "extracted_at": datetime.now().isoformat(),
                "counts": {key: len(extracted[key]) for key in ("risks", "events", "metrics")},
            }
            stats["processed"] += 1
        except Exception as exc:
            stats["errors"] += 1
            print(f"  error {fname}: {exc}")

    entities["risks"] = dedup_entities(entities["risks"], "name")
    entities["events"] = dedup_entities(entities["events"], "name")
    entities["metrics"] = dedup_entities(entities["metrics"], "name")

    payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "risks": len(entities["risks"]),
            "events": len(entities["events"]),
            "metrics": len(entities["metrics"]),
            **stats,
        },
        **entities,
    }
    save_json(ENTITIES_FILE, payload)
    state["updated_at"] = datetime.now().isoformat()
    save_json(STATE_FILE, state)

    print("Entity extraction complete")
    print(f"  processed: {stats['processed']}")
    print(f"  skipped: {stats['skipped']}")
    print(f"  errors: {stats['errors']}")
    print(f"  risks: {len(entities['risks'])}")
    print(f"  events: {len(entities['events'])}")
    print(f"  metrics: {len(entities['metrics'])}")
    print(f"  output: {ENTITIES_FILE}")
    return payload


def write_to_neo4j(entities):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    with driver.session() as session:
        for risk in entities.get("risks", []):
            session.run("""
                MATCH (c:Company {code: $code})
                MATCH (f:Filing {filing_id: $fid})
                MERGE (r:Risk {name: $name})
                SET r.description = $desc, r.confidence = $conf
                MERGE (f)-[:MENTIONS]->(r)
                MERGE (c)-[:HAS_RISK]->(r)
            """, code=risk["stock_code"], fid=risk["source_filing_id"],
                name=risk["name"][:120], desc=risk["description"][:240],
                conf=risk.get("confidence", "medium"))

        for event in entities.get("events", []):
            session.run("""
                MATCH (c:Company {code: $code})
                MATCH (f:Filing {filing_id: $fid})
                MERGE (e:Event {name: $name})
                SET e.type = $etype, e.description = $desc
                MERGE (f)-[:DISCLOSES_EVENT]->(e)
                MERGE (e)-[:AFFECTS]->(c)
            """, code=event["stock_code"], fid=event["source_filing_id"],
                name=event["name"][:120], etype=event["type"],
                desc=event["description"][:240])

        for metric in entities.get("metrics", []):
            session.run("""
                MATCH (c:Company {code: $code})
                MATCH (f:Filing {filing_id: $fid})
                MERGE (m:Metric {name: $name, source_filing_id: $fid})
                SET m.value = $val, m.type = $type
                MERGE (f)-[:DISCLOSES]->(m)
                MERGE (c)-[:HAS_METRIC]->(m)
            """, code=metric["stock_code"], fid=metric["source_filing_id"],
                name=metric["name"], val=metric.get("value", ""),
                type=metric.get("type", ""))

    driver.close()
    print("Neo4j entity graph updated")


def build_chunk_support_relations():
    from neo4j import GraphDatabase

    if not os.path.exists(ENTITIES_FILE):
        return

    entities = load_json(ENTITIES_FILE, empty_entities())
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        for risk in entities.get("risks", []):
            chunk_id = risk.get("source_chunk_id")
            if chunk_id:
                session.run("""
                    MERGE (ch:Chunk {chunk_id: $chunk_id})
                    WITH ch
                    MATCH (r:Risk {name: $name})
                    MERGE (ch)-[:SUPPORTS]->(r)
                """, chunk_id=chunk_id, name=risk["name"][:120])

        for event in entities.get("events", []):
            chunk_id = event.get("source_chunk_id")
            if chunk_id:
                session.run("""
                    MERGE (ch:Chunk {chunk_id: $chunk_id})
                    WITH ch
                    MATCH (e:Event {name: $name})
                    MERGE (ch)-[:SUPPORTS]->(e)
                """, chunk_id=chunk_id, name=event["name"][:120])
    driver.close()
    print("Chunk SUPPORTS relations updated")


def main():
    parser = argparse.ArgumentParser(description="Extract entities and optionally write them to Neo4j")
    parser.add_argument("mode", nargs="?", default="all", choices=["extract", "neo4j", "all"])
    parser.add_argument("--force", action="store_true", help="re-extract all text files")
    args = parser.parse_args()

    if args.mode in ("extract", "all"):
        entities = process_all_stocks(force=args.force)

    if args.mode in ("neo4j", "all"):
        if args.mode == "neo4j":
            entities = load_json(ENTITIES_FILE, empty_entities())
        write_to_neo4j(entities)
        build_chunk_support_relations()


if __name__ == "__main__":
    main()
