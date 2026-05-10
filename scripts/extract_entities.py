#!/usr/bin/env python3
"""
P4 + P5: 实体抽取 + Neo4j图谱构建
从文本/结构化数据中提取风险、事件、指标，写入Neo4j
"""
import json
import os
import sys
import re
from datetime import datetime

from cninfo_paths import DATA_DIR

CHUNK_DIR = os.path.join(DATA_DIR, "chunks")
TEXT_DIR = os.path.join(DATA_DIR, "texts")
STRUCTURED_DIR = os.path.join(DATA_DIR, "structured")
ENTITIES_DIR = os.path.join(DATA_DIR, "entities")
os.makedirs(ENTITIES_DIR, exist_ok=True)

# 财务指标关键词
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
    "基本每股收益": "basic_eps"
}

# 事件类型关键词
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
    "业绩预告": ["业绩预告", "业绩快报", "业绩变动", "业绩预增"]
}

# 风险关键词
RISK_KEYWORDS = [
    "风险", "不确定性", "可能影响", "不利影响", "波动风险",
    "政策风险", "市场风险", "经营风险", "财务风险", "汇率风险",
    "原材料价格", "竞争加剧", "行业波动"
]

def extract_entities_from_text(text: str, stock_code: str, filing_id: str, page_num: int, chunk_id: str) -> dict:
    """从文本中提取风险、事件、指标（基于规则）"""
    results = {"risks": [], "events": [], "metrics": []}
    
    lines = text.split("\n")
    
    # 提取指标
    for keyword, eng_name in METRIC_KEYWORDS.items():
        if keyword in text:
            # 找到关键词前后的数值
            for line in lines:
                if keyword in line:
                    nums = re.findall(r'[-]?\d+[,]?\d*\.?\d+[亿万千]?', line)
                    if nums:
                        results["metrics"].append({
                            "name": keyword,
                            "type": eng_name,
                            "value": nums[0],
                            "context": line.strip()[:100],
                            "source_filing_id": filing_id,
                            "source_page": page_num,
                            "source_chunk_id": chunk_id
                        })
    
    # 提取事件
    for event_type, keywords in EVENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                for line in lines:
                    if kw in line and len(line.strip()) > 10:
                        results["events"].append({
                            "name": line.strip()[:60],
                            "type": event_type,
                            "description": line.strip()[:200],
                            "source_filing_id": filing_id,
                            "source_page": page_num,
                            "source_chunk_id": chunk_id
                        })
                        break
    
    # 提取风险
    for kw in RISK_KEYWORDS:
        if kw in text:
            for line in lines:
                if kw in line and len(line.strip()) > 15:
                    results["risks"].append({
                        "name": line.strip()[:60],
                        "type": "risk",
                        "description": line.strip()[:200],
                        "confidence": "medium",
                        "source_filing_id": filing_id,
                        "source_page": page_num,
                        "source_chunk_id": chunk_id
                    })
                    break
    
    return results

def dedup_entities(entities: list, key: str) -> list:
    """去重实体"""
    seen = set()
    result = []
    for e in entities:
        k = e.get(key, "")[:80]
        if k not in seen:
            seen.add(k)
            result.append(e)
    return result

def process_all_stocks():
    """处理所有股票的文本提取实体"""
    text_files = sorted([f for f in os.listdir(TEXT_DIR) if f.endswith(".json")])
    print(f"📂 处理 {len(text_files)} 个文本文件...")

    all_risks = []
    all_events = []
    all_metrics = []
    
    for i, fname in enumerate(text_files):
        fpath = os.path.join(TEXT_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            continue
        
        filing_id = data.get("filing_id", fname.replace(".json", ""))
        stock_code = data.get("stock_code", "unknown")
        pages = data.get("pages", [])
        
        for page in pages:
            page_num = page.get("page_num", 1)
            text = page.get("text", "")
            chunk_id = f"{filing_id}_chunk_{page_num}_0"
            
            extracted = extract_entities_from_text(text, stock_code, filing_id, page_num, chunk_id)
            
            for r in extracted["risks"]:
                r["stock_code"] = stock_code
                all_risks.append(r)
            for e in extracted["events"]:
                e["stock_code"] = stock_code
                all_events.append(e)
            for m in extracted["metrics"]:
                m["stock_code"] = stock_code
                all_metrics.append(m)
        
        if (i+1) % 50 == 0:
            print(f"  ✅ [{i+1}/{len(text_files)}]")
    
    # 去重
    all_risks = dedup_entities(all_risks, "name")
    all_events = dedup_entities(all_events, "name")
    all_metrics = dedup_entities(all_metrics, "name")
    
    print(f"\n📊 实体抽取结果:")
    print(f"  风险:     {len(all_risks)}")
    print(f"  事件:     {len(all_events)}")
    print(f"  指标:     {len(all_metrics)}")
    
    # 保存到文件
    entities = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "risks": len(all_risks),
            "events": len(all_events),
            "metrics": len(all_metrics)
        },
        "risks": all_risks,
        "events": all_events,
        "metrics": all_metrics
    }
    
    entities_path = os.path.join(ENTITIES_DIR, "extracted_entities.json")
    with open(entities_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 实体已保存: {entities_path}")
    
    return entities

def write_to_neo4j(entities: dict):
    """将实体写入Neo4j"""
    from neo4j import GraphDatabase
    
    uri = "bolt://localhost:7687"
    try:
        driver = GraphDatabase.driver(uri, auth=("neo4j", "neo4j"))
    except Exception as e:
        print(f"❌ Neo4j连接失败: {e}")
        print("   请先启动Neo4j: python3 scripts/neo4j_graph.py start")
        return
    
    with driver.session() as session:
        # 风险节点
        count = 0
        for risk in entities["risks"]:
            try:
                session.run("""
                    MATCH (c:Company {code: $code})
                    MATCH (f:Filing {filing_id: $fid})
                    MERGE (r:Risk {name: $name})
                    SET r.description = $desc, r.confidence = $conf
                    MERGE (f)-[:MENTIONS]->(r)
                    MERGE (c)-[:HAS_RISK]->(r)
                """, code=risk["stock_code"], fid=risk["source_filing_id"],
                     name=risk["name"][:80], desc=risk["description"][:200],
                     conf=risk["confidence"])
                count += 1
            except Exception as e:
                pass
        print(f"  ✅ 写入 {count} 个Risk节点")
        
        # 事件节点
        count = 0
        for event in entities["events"]:
            try:
                session.run("""
                    MATCH (c:Company {code: $code})
                    MATCH (f:Filing {filing_id: $fid})
                    MERGE (e:Event {name: $name})
                    SET e.type = $etype, e.description = $desc
                    MERGE (f)-[:DISCLOSES_EVENT]->(e)
                    MERGE (e)-[:AFFECTS]->(c)
                """, code=event["stock_code"], fid=event["source_filing_id"],
                     name=event["name"][:80], etype=event["type"],
                     desc=event["description"][:200])
                count += 1
            except Exception as e:
                pass
        print(f"  ✅ 写入 {count} 个Event节点")
        
        # 指标节点
        count = 0
        for metric in entities["metrics"]:
            try:
                session.run("""
                    MATCH (c:Company {code: $code})
                    MATCH (f:Filing {filing_id: $fid})
                    MERGE (m:Metric {name: $name})
                    SET m.value = $val, m.type = $type
                    MERGE (f)-[:DISCLOSES]->(m)
                """, code=metric["stock_code"], fid=metric["source_filing_id"],
                     name=metric["name"], val=metric.get("value", ""),
                     type=metric.get("type", ""))
                count += 1
            except Exception as e:
                pass
        print(f"  ✅ 写入 {count} 个Metric节点")
    
    driver.close()
    print("\n📊 Neo4j 图谱更新完成！")

def build_chunk_support_relations():
    """建立Chunk到Risk/Event的SUPPORTS关系"""
    from neo4j import GraphDatabase
    
    uri = "bolt://localhost:7687"
    try:
        driver = GraphDatabase.driver(uri, auth=("neo4j", "neo4j"))
    except:
        return
    
    with driver.session() as session:
        entities_path = os.path.join(ENTITIES_DIR, "extracted_entities.json")
        if not os.path.exists(entities_path):
            return
        
        with open(entities_path) as f:
            entities = json.load(f)
        
        # 为每个风险和事件创建：从文本创建chunk_id，然后建立SUPPORTS关系
        for risk in entities["risks"]:
            chunk_id = risk.get("source_chunk_id", "")
            if chunk_id:
                session.run("""
                    MERGE (ch:Chunk {chunk_id: $chunk_id})
                    MATCH (r:Risk {name: $name})
                    MERGE (ch)-[:SUPPORTS]->(r)
                """, chunk_id=chunk_id, name=risk["name"][:80])
        
        for event in entities["events"]:
            chunk_id = event.get("source_chunk_id", "")
            if chunk_id:
                session.run("""
                    MERGE (ch:Chunk {chunk_id: $chunk_id})
                    MATCH (e:Event {name: $name})
                    MERGE (ch)-[:SUPPORTS]->(e)
                """, chunk_id=chunk_id, name=event["name"][:80])
    
    driver.close()
    print("✅ Chunk-SUPPORTS 关系建立完成")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if mode in ("extract", "all"):
        print("=" * 50)
        print("🔄 P4: 实体抽取")
        print("=" * 50)
        entities = process_all_stocks()
    
    if mode in ("neo4j", "all"):
        print("\n" + "=" * 50)
        print("🔄 P5: Neo4j图谱写入")
        print("=" * 50)
        entities_path = os.path.join(ENTITIES_DIR, "extracted_entities.json")
        if os.path.exists(entities_path):
            with open(entities_path) as f:
                entities = json.load(f)
            write_to_neo4j(entities)
            build_chunk_support_relations()
        else:
            print("❌ 实体文件不存在，请先extract")
    
    if mode == "neo4j-base":
        # 只写入公司和公告
        print("\n" + "=" * 50)
        print("🔄 P5: 基础图谱(Company+Filing)")
        print("=" * 50)
        from neo4j_graph import build_entities_and_graph
        build_entities_and_graph()
