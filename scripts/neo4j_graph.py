#!/usr/bin/env python3
"""
Build the base Neo4j graph for configured stocks and filing metadata.

Default build mode is incremental and idempotent. It never clears the database
unless the explicit "reset" command is used.
"""
import argparse
import json
import os
import subprocess

from cninfo_paths import DATA_DIR
from stock_config import load_stocks

NEO4J_DIR = os.environ.get("NEO4J_HOME", "/opt/data/neo4j")
JAVA_HOME = os.environ.get("JAVA_HOME", "/opt/data/java/jdk-17.0.19+10")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "password")


def setup_neo4j():
    if os.path.exists(NEO4J_DIR):
        print(f"Neo4j already installed: {NEO4J_DIR}")
    else:
        print("Downloading Neo4j Community Edition...")
        import ssl
        import tarfile
        import urllib.request

        ctx = ssl._create_unverified_context()
        url = "https://dist.neo4j.org/neo4j-community-5.26.0-unix.tar.gz"
        tar_path = os.path.join(DATA_DIR, "neo4j.tar.gz")
        extract_dir = os.path.join(DATA_DIR, "neo4j_extract")
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(extract_dir, exist_ok=True)

        with urllib.request.urlopen(url, context=ctx) as response:
            with open(tar_path, "wb") as f:
                f.write(response.read())
        with tarfile.open(tar_path) as tar:
            tar.extractall(path=extract_dir)
        os.rename(os.path.join(extract_dir, "neo4j-community-5.26.0"), NEO4J_DIR)
        os.remove(tar_path)
        print(f"Neo4j installed: {NEO4J_DIR}")

    os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ["NEO4J_HOME"] = NEO4J_DIR

    data_dir = os.path.join(DATA_DIR, "neo4j_data")
    logs_dir = os.path.join(DATA_DIR, "neo4j_logs")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    cfg_path = os.path.join(NEO4J_DIR, "conf", "neo4j.conf")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(f"""
server.directories.data={data_dir}
server.directories.logs={logs_dir}
server.bolt.enabled=true
server.bolt.listen_address=:7687
server.http.enabled=true
server.http.listen_address=:7474
dbms.security.auth_enabled=false
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2g
dbms.memory.pagecache.size=512m
""".strip())

    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:7474", timeout=2)
        print("Neo4j is already running")
        return
    except Exception:
        pass

    print("Starting Neo4j...")
    result = subprocess.run(
        [os.path.join(NEO4J_DIR, "bin", "neo4j"), "start"],
        capture_output=True,
        text=True,
        env={**os.environ, "JAVA_HOME": JAVA_HOME, "NEO4J_HOME": NEO4J_DIR},
        check=False,
    )
    if result.stdout:
        print(result.stdout[-500:])
    if result.stderr:
        print(result.stderr[-500:])


def load_filing_index():
    index_path = os.path.join(DATA_DIR, "filings", "filing_index.json")
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"filing_index.json not found: {index_path}")
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_constraints(session):
    session.run("CREATE CONSTRAINT company_code IF NOT EXISTS FOR (c:Company) REQUIRE c.code IS UNIQUE")
    session.run("CREATE CONSTRAINT filing_id IF NOT EXISTS FOR (f:Filing) REQUIRE f.filing_id IS UNIQUE")
    session.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE")


def write_companies(session, stock_map):
    for code, name in stock_map.items():
        session.run(
            """
            MERGE (c:Company {code: $code})
            SET c.name = $name
            """,
            code=code,
            name=name,
        )


def write_filings(session, filings, stock_map):
    count = 0
    for filing in filings:
        stock_code = filing.get("stock_code", "")
        if stock_code not in stock_map:
            continue
        session.run(
            """
            MATCH (c:Company {code: $stock_code})
            MERGE (f:Filing {filing_id: $filing_id})
            SET f.title = $title,
                f.type = $filing_type,
                f.publish_date = $publish_date,
                f.report_period = $report_period,
                f.source_url = $source_url,
                f.local_file_path = $local_file_path,
                f.parse_status = $parse_status,
                f.stock_code = $stock_code
            MERGE (c)-[:FILES]->(f)
            """,
            stock_code=stock_code,
            filing_id=filing["filing_id"],
            title=filing.get("announcement_title", ""),
            filing_type=filing.get("announcement_type", ""),
            publish_date=filing.get("publish_date", ""),
            report_period=filing.get("report_period", ""),
            source_url=filing.get("source_url", ""),
            local_file_path=filing.get("local_file_path", ""),
            parse_status=filing.get("parse_status", "pending"),
        )
        count += 1
    return count


def mark_text_extracted(session):
    text_dir = os.path.join(DATA_DIR, "texts")
    if not os.path.exists(text_dir):
        return 0

    count = 0
    for filename in os.listdir(text_dir):
        if not filename.endswith(".json"):
            continue
        filing_id = filename[:-5]
        session.run(
            """
            MATCH (f:Filing {filing_id: $filing_id})
            SET f.has_text = true
            """,
            filing_id=filing_id,
        )
        count += 1
    return count


def build_graph(reset=False):
    from neo4j import GraphDatabase

    stock_map = {stock["code"]: stock["name"] for stock in load_stocks()}
    filings = load_filing_index().get("filings", [])

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        if reset:
            session.run("MATCH (n) DETACH DELETE n")
            print("Neo4j graph reset")

        ensure_constraints(session)
        write_companies(session, stock_map)
        filing_count = write_filings(session, filings, stock_map)
        text_count = mark_text_extracted(session)

        result = session.run("""
            MATCH (c:Company)
            OPTIONAL MATCH (c)-[:FILES]->(f:Filing)
            RETURN c.code AS code, c.name AS name, count(f) AS filing_count
            ORDER BY c.code
        """)
        print("Neo4j graph updated")
        print(f"  companies: {len(stock_map)}")
        print(f"  filings merged: {filing_count}")
        print(f"  text flags updated: {text_count}")
        for row in result:
            print(f"  {row['name']} ({row['code']}): {row['filing_count']} filings")

    driver.close()


def main():
    parser = argparse.ArgumentParser(description="Setup and build Neo4j graph")
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["setup", "build", "reset", "all"],
        help="setup installs/starts Neo4j, build is incremental, reset clears then rebuilds",
    )
    args = parser.parse_args()

    if args.command in ("setup", "all"):
        setup_neo4j()
    if args.command in ("build", "all"):
        build_graph(reset=False)
    if args.command == "reset":
        build_graph(reset=True)


if __name__ == "__main__":
    main()
