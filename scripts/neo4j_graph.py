#!/usr/bin/env python3
"""
P4-1 + P4-2 + P5: Neo4j知识图谱 — 节点和关系的构建
支持所有5只股票的Company + Filing节点写入
"""
import json
import os
import sys
import subprocess
from datetime import datetime

DATA_DIR = os.environ.get("CNINFO_DATA_DIR", "/tmp/cninfo_watch")
NEO4J_DIR = "/opt/data/neo4j"
JAVA_HOME = "/opt/data/java/jdk-17.0.19+10"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "password"

def setup_neo4j():
    """安装并启动Neo4j"""
    if os.path.exists(NEO4J_DIR):
        print("✅ Neo4j 已安装")
    else:
        print("📥 下载 Neo4j Community Edition...")
        import urllib.request, ssl, tarfile
        ctx = ssl._create_unverified_context()
        url = "https://dist.neo4j.org/neo4j-community-5.26.0-unix.tar.gz"
        req = urllib.request.urlopen(url, context=ctx)
        tar_path = "/tmp/neo4j.tar.gz"
        with open(tar_path, "wb") as f:
            f.write(req.read())
        print("📦 解压...")
        os.makedirs("/tmp/neo4j_extract", exist_ok=True)
        with tarfile.open(tar_path) as tar:
            tar.extractall(path="/tmp/neo4j_extract")
        os.rename(f"/tmp/neo4j_extract/neo4j-community-5.26.0", NEO4J_DIR)
        os.remove(tar_path)
        print(f"✅ Neo4j 安装完成: {NEO4J_DIR}")
    
    # 启动
    os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ["NEO4J_HOME"] = NEO4J_DIR
    os.makedirs("/tmp/cninfo_watch/neo4j_data", exist_ok=True)
    os.makedirs("/tmp/cninfo_watch/neo4j_logs", exist_ok=True)
    
    # 配置
    cfg_path = os.path.join(NEO4J_DIR, "conf", "neo4j.conf")
    with open(cfg_path, "w") as f:
        f.write(f"""
server.directories.data=/tmp/cninfo_watch/neo4j_data
server.directories.logs=/tmp/cninfo_watch/neo4j_logs
server.bolt.enabled=true
server.bolt.listen_address=:7687
server.http.enabled=true
server.http.listen_address=:7474
dbms.security.auth_enabled=false
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2g
dbms.memory.pagecache.size=512m
""".strip())
    
    # 检查是否已在运行
    try:
        import urllib.request
        r = urllib.request.urlopen("http://localhost:7474", timeout=2)
        print("✅ Neo4j 已在运行")
        return
    except:
        pass
    
    print("🚀 启动 Neo4j...")
    result = subprocess.run(
        [os.path.join(NEO4J_DIR, "bin", "neo4j"), "start"],
        capture_output=True, text=True,
        env={**os.environ, "JAVA_HOME": JAVA_HOME, "NEO4J_HOME": NEO4J_DIR}
    )
    print(result.stdout[-500:] if result.stdout else "")
    print(result.stderr[-500:] if result.stderr else "")
    
    import time, urllib.request
    for attempt in range(10):
        try:
            r = urllib.request.urlopen("http://localhost:7474", timeout=2)
            print(f"✅ Neo4j 已就绪 (等待 {attempt+1}秒)")
            return
        except:
            time.sleep(1)
    print("⚠️ Neo4j 启动超时，请手动检查")

def build_graph():
    """构建知识图谱"""
    print("=" * 50)
    print("📊 P4-2: 构建Neo4j知识图谱")
    print("=" * 50)
    
    os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ["NEO4J_HOME"] = NEO4J_DIR
    
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    
    STOCK_MAP = {
        "600089": "特变电工",
        "600790": "轻纺城",
        "600824": "益民集团",
        "600927": "永安期货",
        "601186": "中国铁建"
    }
    
    with driver.session() as session:
        # 清空
        session.run("MATCH (n) DETACH DELETE n")
        print("🧹 清空图谱")
        
        # 建立约束
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.code IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Filing) REQUIRE f.filing_id IS UNIQUE")
        print("✅ 约束创建完成")
        
        # 创建Company节点
        for code, name in STOCK_MAP.items():
            session.run(
                "MERGE (c:Company {code: $code}) SET c.name = $name",
                code=code, name=name
            )
        print(f"✅ 写入 {len(STOCK_MAP)} 个Company节点")
        
        # 加载filing_index
        idx_path = os.path.join(DATA_DIR, "filings", "filing_index.json")
        with open(idx_path) as f:
            idx = json.load(f)
        
        filings = idx.get("filings", [])
        
        # 批量写入Filing节点 + Company关系
        BATCH = 50
        for i in range(0, len(filings), BATCH):
            batch = filings[i:i+BATCH]
            for fi in batch:
                sc = fi.get("stock_code", "")
                if sc not in STOCK_MAP:
                    continue
                session.run("""
                    MATCH (c:Company {code: $sc})
                    MERGE (f:Filing {
                        filing_id: $fid,
                        title: $title,
                        type: $ftype,
                        publish_date: $pub_date,
                        report_period: $rperiod,
                        source_url: $surl,
                        local_file_path: $lpath,
                        parse_status: $pstatus
                    })
                    MERGE (c)-[:FILES]->(f)
                """, sc=sc, fid=fi["filing_id"],
                    title=fi.get("announcement_title", ""),
                    ftype=fi.get("announcement_type", ""),
                    pub_date=fi.get("publish_date", ""),
                    rperiod=fi.get("report_period", ""),
                    surl=fi.get("source_url", ""),
                    lpath=fi.get("local_file_path", ""),
                    pstatus=fi.get("parse_status", "pending"))
            
            print(f"  写入 {min(i+BATCH, len(filings))}/{len(filings)} 个Filing节点...")
        
        print(f"✅ 写入 {len(filings)} 个Filing节点及其关系")
        
        # 检查文本文件存在性，创建Chunk节点
        TEXT_DIR = os.path.join(DATA_DIR, "texts")
        chunk_count = 0
        for fn in os.listdir(TEXT_DIR):
            if not fn.endswith(".json"): continue
            fid = fn.replace(".json", "")
            session.run("""
                MATCH (f:Filing {filing_id: $fid})
                SET f.has_text = true
            """, fid=fid)
            chunk_count += 1
        
        print(f"✅ 标记 {chunk_count} 个Filing有文本")
        
        # 统计
        result = session.run("""
            MATCH (c:Company)
            RETURN c.code, c.name,
                size((c)-[:FILES]->()) as filing_count
            ORDER BY c.code
        """)
        print("\n📊 图谱统计:")
        for r in result:
            print(f"  {r['c.name']} ({r['c.code']}): {r['filing_count']} 份公告")
        
        result = session.run("MATCH (n) RETURN count(n) as total, labels(n) as labels")
        print(f"\n📊 总节点数: {[r for r in result]}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_neo4j()
    elif len(sys.argv) > 1 and sys.argv[1] == "build":
        build_graph()
    else:
        setup_neo4j()
        build_graph()

if __name__ == "__main__":
    main()
