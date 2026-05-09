#!/usr/bin/env python3
"""
P6: LLM Wiki研究页生成
生成公司页、年报分析页、风险页、事件页 (Markdown格式)
"""
import json
import os
from datetime import datetime

DATA_DIR = os.environ.get("CNINFO_DATA_DIR", "/tmp/cninfo_watch")
TEXT_DIR = os.path.join(DATA_DIR, "texts")
CHUNK_DIR = os.path.join(DATA_DIR, "chunks")
STRUCTURED_DIR = os.path.join(DATA_DIR, "structured")
ENTITIES_DIR = os.path.join(DATA_DIR, "entities")
WIKI_DIR = os.path.join(DATA_DIR, "wiki")

STOCK_MAP = {
    "600089": "特变电工",
    "600790": "轻纺城",
    "600824": "益民集团",
    "600927": "永安期货",
    "601186": "中国铁建"
}

def ensure_dirs():
    for d in ["companies", "filings", "risks", "events"]:
        os.makedirs(os.path.join(WIKI_DIR, d), exist_ok=True)

def load_entities():
    """加载已抽取的实体"""
    path = os.path.join(ENTITIES_DIR, "extracted_entities.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"risks": [], "events": [], "metrics": []}

def load_filings(stock_code: str):
    """加载某股票的公告列表"""
    path = os.path.join(DATA_DIR, "filings", "filing_index.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        index = json.load(f)
    return [f for f in index["filings"] if f["stock_code"] == stock_code]

def load_akshare_data():
    """加载AKShare数据"""
    result = {"info": {}, "finance": {}, "daily": {}}
    info_path = os.path.join(STRUCTURED_DIR, "stock_info.json")
    if os.path.exists(info_path):
        with open(info_path) as f:
            result["info"] = json.load(f)
    fins_path = os.path.join(STRUCTURED_DIR, "financial_indicators.json")
    if os.path.exists(fins_path):
        with open(fins_path) as f:
            result["finance"] = json.load(f)
    daily_path = os.path.join(STRUCTURED_DIR, "daily_history.json")
    if os.path.exists(daily_path):
        with open(daily_path) as f:
            result["daily"] = json.load(f)
    return result

def generate_company_page(stock_code: str, name: str):
    """生成公司研究页"""
    filings = load_filings(stock_code)
    entities = load_entities()
    akshare = load_akshare_data()
    
    # 按类型统计
    by_type = {}
    for f in filings:
        t = f.get("announcement_type", "unknown")
        by_type.setdefault(t, 0)
        by_type[t] += 1
    
    # 公司事件
    company_events = [e for e in entities.get("events", []) if e.get("stock_code") == stock_code]
    # 公司风险
    company_risks = [r for r in entities.get("risks", []) if r.get("stock_code") == stock_code]
    # 公司指标
    company_metrics = [m for m in entities.get("metrics", []) if m.get("stock_code") == stock_code]
    
    lines = []
    lines.append(f"# {name} ({stock_code}) 研究页\n")
    lines.append(f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"> 数据来源: 巨潮资讯网 (cninfo.com.cn) | AKShare | 上海证券交易所\n")
    lines.append(f"> 本页面自动生成，所有证据可追溯至原文\n")
    
    # 基本信息
    lines.append("## 📋 基本信息\n")
    info = akshare.get("info", {}).get(stock_code, {})
    if info and "error" not in info:
        for k, v in info.items():
            lines.append(f"- **{k}**: {v}\n")
    else:
        lines.append(f"- **股票代码**: {stock_code}\n")
        lines.append(f"- **公司名称**: {name}\n")
    lines.append("")
    
    # 核心财务指标
    lines.append("## 📊 核心财务指标\n")
    fin = akshare.get("finance", {}).get(stock_code, {})
    if fin and "error" not in fin:
        for k, v in list(fin.items())[:15]:
            lines.append(f"- **{k}**: {v}\n")
    else:
        lines.append("（数据待补充）\n")
    lines.append("")
    
    # 公告统计
    lines.append("## 📄 公告统计\n")
    lines.append(f"- **总公告数**: {len(filings)}\n")
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"  - {t}: {c} 份\n")
    lines.append("")
    
    # 近期公告列表
    lines.append("## 📑 近期公告\n")
    sorted_filings = sorted(filings, key=lambda x: x.get("publish_date", ""), reverse=True)[:20]
    for f in sorted_filings:
        title = f.get("announcement_title", "")
        pub_date = f.get("publish_date", "")
        ftype = f.get("announcement_type", "")
        status = "✅" if f.get("parse_status") == "chunked" else "⏳"
        lines.append(f"- {status} **{pub_date}** [{ftype}] {title[:60]}\n")
    lines.append("")
    
    # 重大事件
    lines.append("## 🔔 重大事件\n")
    if company_events:
        for e in company_events[:20]:
            lines.append(f"- **{e.get('type', '')}**: {e.get('name', '')}\n")
            lines.append(f"  - 来源: `{e.get('source_filing_id', '')}` 第{e.get('source_page', '')}页\n")
    else:
        lines.append("（待LLM抽取）\n")
    lines.append("")
    
    # 风险汇总
    lines.append("## ⚠️ 风险汇总\n")
    if company_risks:
        for r in company_risks[:15]:
            lines.append(f"- {r.get('name', '')}\n")
            lines.append(f"  - 置信度: {r.get('confidence', 'medium')} | 来源: {r.get('source_filing_id', '')}\n")
    else:
        lines.append("（待LLM抽取）\n")
    lines.append("")
    
    # 管理层讨论重点(占位)
    lines.append("## 📝 管理层讨论重点\n")
    lines.append("> 此部分将在LLM深度分析后生成\n")
    lines.append("")
    
    # 待跟踪问题
    lines.append("## 🔍 待跟踪问题\n")
    lines.append("- [ ] 最新季报经营趋势分析\n")
    lines.append("- [ ] 主要风险变化跟踪\n")
    lines.append("- [ ] 重大事件进展\n")
    lines.append("- [ ] 行业对比分析\n")
    lines.append("")
    
    # 原文证据索引
    lines.append("## 📚 原文证据索引\n")
    lines.append(f"全部公告PDF已归档于: `{DATA_DIR}/pdfs/{stock_code}/`\n")
    lines.append(f"文本抽取文件: `{DATA_DIR}/texts/`\n")
    lines.append(f"Chunk向量索引: `{DATA_DIR}/chromadb/`\n")
    lines.append(f"Neo4j图谱: `bolt://localhost:7687`\n")
    lines.append("")
    lines.append("### RAG查询示例\n")
    lines.append("```bash\n")
    lines.append(f"python3 scripts/rag_query.py '近三年主要风险' {stock_code}\n")
    lines.append("```\n")
    
    content = "".join(lines)
    path = os.path.join(WIKI_DIR, "companies", f"{stock_code}-{name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ 公司页: {stock_code}-{name}.md ({len(content)} 字符)")
    return path

def generate_filing_pages(stock_code: str, name: str):
    """生成年报分析页"""
    filings = load_filings(stock_code)
    
    # 只处理年报
    annual_filings = [f for f in filings if f.get("announcement_type") in ("annual_report", "semi_annual_report")]
    
    for f in annual_filings[:5]:  # 最近5份
        fid = f["filing_id"]
        title = f.get("announcement_title", "")
        pub_date = f.get("publish_date", "")
        ftype = "年报分析" if f.get("announcement_type") == "annual_report" else "半年报分析"
        
        lines = []
        lines.append(f"# {title}\n")
        lines.append(f"> **公司**: {name} ({stock_code})\n")
        lines.append(f"> **发布日期**: {pub_date}\n")
        lines.append(f"> **类型**: {ftype}\n")
        lines.append(f"> **filing_id**: {fid}\n")
        lines.append(f"> **PDF路径**: {f.get('local_file_path', 'N/A')}\n")
        lines.append("")
        lines.append("## 📄 文档概要\n")
        lines.append("> 此页面将在LLM深度分析后填充\n")
        lines.append("")
        lines.append("## 📊 关键财务指标\n")
        lines.append("（待提取）\n")
        lines.append("")
        lines.append("## 🎯 管理层讨论与分析\n")
        lines.append("（待提取）\n")
        lines.append("")
        lines.append("## ⚠️ 风险提示\n")
        lines.append("（待提取）\n")
        lines.append("")
        lines.append("## 🔗 相关原文\n")
        lines.append("- 巨潮网原文链接: [查看]({url})\n".format(url=f.get("source_url", "#")))
        lines.append(f"- 本地PDF: `{f.get('local_file_path', 'N/A')}`\n")
        lines.append(f"- 文本抽取: `{DATA_DIR}/texts/{fid}.json`\n")
        lines.append("")
        
        content = "".join(lines)
        year = pub_date[:4] if pub_date else "unknown"
        path = os.path.join(WIKI_DIR, "filings", f"{stock_code}-{year}-{ftype}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ 年报分析页: {stock_code}-{year}-{ftype}.md")

def generate_risk_pages():
    """生成风险页"""
    entities = load_entities()
    risks = entities.get("risks", [])
    
    risk_groups = {}
    for r in risks:
        name = r.get("name", "unknown")[:40]
        if name not in risk_groups:
            risk_groups[name] = []
        risk_groups[name].append(r)
    
    for risk_name, instances in risk_groups.items():
        lines = []
        lines.append(f"# {risk_name}\n")
        lines.append(f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append("")
        lines.append("## 涉及的公司\n")
        companies = set(i.get("stock_code", "") for i in instances)
        for c in companies:
            cn = STOCK_MAP.get(c, c)
            lines.append(f"- {cn} ({c})\n")
        lines.append("")
        lines.append("## 来源证据\n")
        for i in instances[:10]:
            fid = i.get("source_filing_id", "")
            page = i.get("source_page", "")
            lines.append(f"- 来源: `{fid}` 第{page}页\n")
        lines.append("")
        
        content = "".join(lines)
        safe_name = risk_name.replace("/", "·").replace(" ", "_")[:50]
        path = os.path.join(WIKI_DIR, "risks", f"{safe_name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def generate_event_pages():
    """生成事件页"""
    entities = load_entities()
    events = entities.get("events", [])
    
    for e in events[:30]:
        name = e.get("name", "unknown")[:40]
        etype = e.get("type", "")
        
        lines = []
        lines.append(f"# {name}\n")
        lines.append(f"- **类型**: {etype}\n")
        lines.append(f"- **公司**: {STOCK_MAP.get(e.get('stock_code',''), e.get('stock_code',''))}\n")
        lines.append(f"")
        lines.append("## 描述\n")
        lines.append(f"{e.get('description', '')}\n")
        lines.append("")
        lines.append("## 来源证据\n")
        lines.append(f"- 公告ID: `{e.get('source_filing_id', '')}`\n")
        lines.append(f"- 页码: {e.get('source_page', '')}\n")
        lines.append(f"- Chunk: `{e.get('source_chunk_id', '')}`\n")
        lines.append("")
        
        content = "".join(lines)
        safe_name = f"{e.get('stock_code', 'unknown')}-{name}".replace("/", "·").replace(" ", "_")[:50]
        path = os.path.join(WIKI_DIR, "events", f"{safe_name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def generate_wiki_index():
    """生成Wiki主页索引"""
    lines = []
    lines.append("# 📚 证券研究知识库\n")
    lines.append(f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("> 数据来源: 巨潮资讯网(cninfo.com.cn) | AKShare | 上海证券交易所\n")
    lines.append("")
    lines.append("## 系统架构\n")
    lines.append("```\n")
    lines.append("巨潮网PDF → 文本提取 → Chunk切分 → 向量索引(ChromaDB) \n")
    lines.append("                                            ↓\n")
    lines.append("AKShare数据 → 结构化存储 → Neo4j图谱 → RAG问答\n")
    lines.append("                                            ↓\n")
    lines.append("                                        LLM Wiki研究页\n")
    lines.append("```\n")
    lines.append("")
    lines.append("## 📂 数据目录\n")
    lines.append(f"- 公告PDF: `{DATA_DIR}/pdfs/`\n")
    lines.append(f"- 文本提取: `{DATA_DIR}/texts/`\n")
    lines.append(f"- Chunk索引: `{DATA_DIR}/chunks/`\n")
    lines.append(f"- 向量索引: `{DATA_DIR}/chromadb/`\n")
    lines.append(f"- 结构化数据: `{DATA_DIR}/structured/`\n")
    lines.append(f"- Neo4j: `bolt://localhost:7687`\n")
    lines.append("")
    
    # 公司列表
    lines.append("## 🏢 公司研究页\n")
    companies_dir = os.path.join(WIKI_DIR, "companies")
    if os.path.isdir(companies_dir):
        pages = sorted(os.listdir(companies_dir))
        for p in pages:
            if p.endswith(".md"):
                lines.append(f"- [{p.replace('.md','')}](companies/{p})\n")
    lines.append("")
    
    # 年报分析
    lines.append("## 📄 年报分析页\n")
    filings_dir = os.path.join(WIKI_DIR, "filings")
    if os.path.isdir(filings_dir):
        pages = sorted(os.listdir(filings_dir))
        for p in pages:
            if p.endswith(".md"):
                lines.append(f"- [{p.replace('.md','')}](filings/{p})\n")
    lines.append("")
    
    # 风险页
    lines.append("## ⚠️ 风险页\n")
    risks_dir = os.path.join(WIKI_DIR, "risks")
    if os.path.isdir(risks_dir):
        pages = sorted(os.listdir(risks_dir))
        for p in pages[:20]:
            if p.endswith(".md"):
                lines.append(f"- [{p.replace('.md','')}](risks/{p})\n")
    lines.append("")
    
    # 事件页
    lines.append("## 🔔 事件页\n")
    events_dir = os.path.join(WIKI_DIR, "events")
    if os.path.isdir(events_dir):
        pages = sorted(os.listdir(events_dir))
        for p in pages[:20]:
            if p.endswith(".md"):
                lines.append(f"- [{p.replace('.md','')}](events/{p})\n")
    lines.append("")
    
    lines.append("---\n")
    lines.append("## 🔧 使用指南\n")
    lines.append("### RAG问答\n")
    lines.append("```bash\n")
    lines.append("python3 scripts/rag_query.py '问题' 股票代码\n")
    lines.append("```\n")
    lines.append("### Neo4j查询\n")
    lines.append("浏览器打开 http://localhost:7474 输入Cypher:\n")
    lines.append("```cypher\n")
    lines.append("MATCH (c:Company)-[:FILES]->(f:Filing) WHERE c.code='600089' RETURN c,f LIMIT 20\n")
    lines.append("```\n")
    lines.append("### AKShare数据刷新\n")
    lines.append("```bash\n")
    lines.append("python3 scripts/fetch_akshare.py\n")
    lines.append("```\n")
    
    content = "".join(lines)
    path = os.path.join(WIKI_DIR, "README.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ Wiki主页: README.md")

def main():
    print("=" * 50)
    print("📚 P6: LLM Wiki 研究页生成")
    print("=" * 50)
    
    ensure_dirs()
    
    # 公司页
    print("\n🏢 生成公司研究页...")
    for code, name in STOCK_MAP.items():
        generate_company_page(code, name)
    
    # 年报分析页
    print("\n📄 生成年报分析页...")
    for code, name in STOCK_MAP.items():
        generate_filing_pages(code, name)
    
    # 风险页
    print("\n⚠️ 生成风险页...")
    generate_risk_pages()
    
    # 事件页
    print("\n🔔 生成事件页...")
    generate_event_pages()
    
    # Wiki主页
    print("\n📑 生成Wiki主页...")
    generate_wiki_index()
    
    # 统计
    pages = []
    for root, dirs, files in os.walk(WIKI_DIR):
        for f in files:
            if f.endswith(".md"):
                pages.append(os.path.join(root, f))
    
    print(f"\n{'='*50}")
    print(f"📊 Wiki生成报告")
    print(f"  公司研究页:   {len([p for p in pages if '/companies/' in p])}")
    print(f"  年报分析页:   {len([p for p in pages if '/filings/' in p])}")
    print(f"  风险页:       {len([p for p in pages if '/risks/' in p])}")
    print(f"  事件页:       {len([p for p in pages if '/events/' in p])}")
    print(f"  总计:         {len(pages)} 个Markdown页面")
    print(f"  Wiki目录:     {WIKI_DIR}")

if __name__ == "__main__":
    main()
