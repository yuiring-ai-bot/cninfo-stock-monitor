# cninfo-stock-monitor — 基于巨潮公告的证券研究知识库

基于巨潮资讯网公告的证券研究资料整理系统，实现"公告原文可追溯、财务指标可查询、风险事件可关联、研究结论可复盘"的全流程知识库构建。

**技术栈**: Python · PyMuPDF · ChromaDB · Neo4j · AKShare · LLM Wiki

---

## 项目概览

| 数据源 | 角色 | 内容 |
|--------|------|------|
| **巨潮网** | 核心证据源 | 年报/半年报/季报/临时公告 PDF 原文 |
| **AKShare** | 补充数据源 | 行情、市值、行业分类、财务指标、分红 |
| **Neo4j** | 关系图谱 | 公司-公告-指标-风险-事件 关系网络 |
| **ChromaDB** | 向量检索 | PDF 原文切片嵌入，支持语义 RAG 问答 |

### 适用场景

- 个股深度研究：从年报原文检索特定财务数据
- 风险事件追踪：关联公告→风险→公司 的因果关系
- 多股横向比较：通过结构化指标快速对比
- LLM 知识库：基于真实公告原文的 RAG 问答

---

## 快速开始

### 环境要求

- Python 3.10+
- Neo4j 5.x（可选，图谱功能需要）
- pip 包依赖（见各脚本头部）

### 安装依赖

```bash
pip install pymupdf chromadb neo4j akshare pandas
```

### 数据目录

运行数据默认输出到 `/tmp/cninfo_watch/`，可用环境变量覆盖：

```bash
export CNINFO_DATA_DIR=/path/to/data
```

### 高频拉取与模型解耦

高频调度只做公告元数据拉取，不调用任何大模型：

```bash
python scripts/poll_announcements.py --output /path/to/latest_announcements.json
```

GitHub Actions 中的 `Poll cninfo announcements` workflow 每 5 分钟运行一次，只负责：

1. 从巨潮拉取公告元数据。
2. 更新本地轮询状态。
3. 上传 `latest_announcements.json` artifact。

模型分析必须走独立的手动 workflow 或离线脚本，显式读取某次拉取结果。无新增公告时不能触发模型调用，避免无意义 token 消耗。

必要且有用的模型调用并不被禁止，但必须统一经过 `scripts/model_gateway.py`。该入口会先用简单代码逻辑判断输入是否值得分析，例如 `has_new=false` 或 `new_count=0` 时直接退出，不允许消耗 token。外部模型 provider 的接入也应集中写在这个文件里，不应散落在轮询、抓取、PDF 下载或索引脚本中。

---

## 项目结构

```
cninfo-stock-monitor/
├── scripts/
│   ├── watch_stock_cninfo.py      # 单股实时监控（增量，巨潮网API）
│   ├── watch_stock_em.py          # 东方财富API监控
│   ├── watch_stock.py             # 全市场筛选监控
│   ├── fetch_history.py           # 历史公告数据抓取
│   ├── onboard_stock.py           # 新股录入（批量抓取历史）
│   ├── daily_summary.py           # 多股每日摘要
│   ├── poll_announcements.py      # 高频公告轮询（不调用模型）
│   ├── cninfo_resolver.py         # 股票元数据解析（orgId查询）
│   ├── cninfo_pdfs.py             # PDF下载引擎
│   ├── fetch_pdfs.py              # PDF下载命令行包装
│   │
│   ├── extract_pdfs.py            # ▶ P2: 批量PDF文本提取（PyMuPDF）
│   ├── build_rag_index.py         # ▶ P2: 文本切分 + ChromaDB向量索引
│   ├── rag_query.py               # ▶ P2: RAG语义问答接口
│   ├── fetch_akshare.py           # ▶ P3: AKShare财务/行情数据接入
│   ├── extract_entities.py        # ▶ P5: 规则引擎实体抽取（风险/事件/指标）
│   ├── neo4j_graph.py             # ▶ P4: Neo4j知识图谱写入
│   └── generate_wiki.py           # ▶ P6: LLM Wiki研究页生成
├── config/
│   └── stocks.json                # 批量监控股票配置
├── docs/
│   └── ARCHITECTURE.md            # 完整架构文档
├── .gitignore
├── LICENSE
└── README.md
```

---

## 管线流程

### 阶段 1: 数据获取（P0-P1）
```bash
# ① 录入新股元数据
python scripts/onboard_stock.py 600089 特变电工

# ② 批量下载PDF
python scripts/fetch_pdfs.py

# ③ 定时监控增量公告
python scripts/watch_stock_cninfo.py 600089 特变电工

# ④ 日终摘要
python scripts/daily_summary.py
```

### 阶段 2: 文本提取与RAG（P2）
```bash
# ① PDF → 结构化文本（带页码）
python scripts/extract_pdfs.py

# ② 文本切分 + ChromaDB向量索引（增量构建，支持断点续跑）
python scripts/build_rag_index.py

# ③ RAG问答（语义检索+原文追溯）
python scripts/rag_query.py '特变电工2024年营业收入和净利润情况如何？' 600089
```

### 阶段 3: 结构化数据（P3-P6）
```bash
# ① AKShare财务数据
python scripts/fetch_akshare.py

# ② 风险/事件/指标实体抽取
python scripts/extract_entities.py

# ③ Neo4j知识图谱写入
python scripts/neo4j_graph.py

# ④ LLM Wiki研究页生成
python scripts/generate_wiki.py
```

---

## RAG问答

```bash
# 单股问答 — 自动检索相关年报/公告切片段落
python scripts/rag_query.py '公司2024年研发投入多少？' 600089

# 输出包含：来源公告标题、页码、发布日期、相关度评分
```

### 检索字段

| 字段 | 说明 |
|------|------|
| `filing_id` | 巨潮公告唯一ID |
| `stock_code` | 股票代码 |
| `page_num` | PDF原文页码 |
| `title` | 公告标题 |
| `publish_date` | 发布日期 |
| `type` | 公告类型（annual_report / semi_annual_report / temporary_announcement） |

---

## Neo4j 知识图谱

### 节点类型

| 节点 | 标签 | 数量 |
|------|------|------|
| 上市公司 | `Company` | 5 |
| 公告 | `Filing` | 336 |
| 风险事件 | `Risk` | 2,404 |
| 重大事项 | `Event` | 4,871 |
| 财务指标 | `Metric` | 10 |

### 示例查询

```cypher
// 查询某公司的风险分布
MATCH (c:Company {code: '600089'})-[:FILES]->(f:Filing)-[:MENTIONS]->(r:Risk)
RETURN r.name, count(*) as cnt ORDER BY cnt DESC

// 关联重大事项
MATCH (c:Company {code: '600089'})-[*2]-(e:Event)
RETURN e.name, e.date LIMIT 20
```

---

## 公告类型对照

| category_code | 说明 | filing_type |
|--------------|------|-------------|
| `category_ndbg_szsh` | 年度报告 | `annual_report` |
| `category_bndbg_szsh` | 半年度报告 | `semi_annual_report` |
| `category_jdbg_szsh` | 季度报告 | `quarterly_report` |
| `category_yjygjxz` | 业绩预告/快报 | `earnings_forecast` |
| 其他 | 临时公告 | `temporary_announcement` |

---

## 配置

### 监控股票列表 (`config/stocks.json`)

```json
{
  "stocks": [
    { "code": "600089", "name": "特变电工" },
    { "code": "600790", "name": "轻纺城" },
    { "code": "600824", "name": "益民集团" },
    { "code": "600927", "name": "永安期货" },
    { "code": "601186", "name": "中国铁建" }
  ]
}
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CNINFO_DATA_DIR` | 运行数据目录 | `/tmp/cninfo_watch` |
| `CNINFO_STOCK_CONFIG` | 股票配置文件路径 | `config/stocks.json` |

---

## 新增股票操作手册

以新增"国泰君安 (601211)"为例，按顺序执行以下 10 步：

| 步骤 | 阶段 | 命令 | 增量/全量 | 耗时 |
|------|------|------|----------|------|
| 1 | P0 | `python3 scripts/fetch_history.py 601211 国泰君安` | 增量 | 1-3min |
| 2 | P1 | `python3 scripts/fetch_pdfs.py` | 增量 | 5-20min |
| 3 | 配置 | 编辑 `config/stocks.json` 添加新条目 | — | 手动 |
| 4 | P2-2 | `python3 scripts/extract_pdfs.py` | 增量(pending) | 2-10min |
| 5 | P2-3 | `python3 scripts/build_rag_index.py` | 增量(checkpoint) | 2-8min |
| 6 | P3 | `python3 scripts/fetch_akshare.py` | 全量(覆盖) | 1-3min |
| 7 | P5 | `python3 scripts/extract_entities.py` | 全量(覆盖) | 2-5min |
| 8 | P4 | `python3 scripts/neo4j_graph.py` | **全量重建** | 5-15min |
| 9 | P6 | `python3 scripts/generate_wiki.py` | 全量(覆盖) | 1-3min |
| 10 | 验证 | `python3 scripts/rag_query.py '国泰君安2024年主营业务' 601211` | — | 即时 |

### 关键注意事项

1. **步骤 3 必须在步骤 4 之前完成** — P2-P6 所有脚本通过 `stock_config.load_stocks()` 读取 `config/stocks.json`，不更新则新股票不会被处理
2. **ChromaDB 索引增量安全** — `build_rag_index.py` 使用 `get_or_create_collection` + checkpoint，不会丢失已有向量
3. **Neo4j 全量重建** — `neo4j_graph.py` 会清空旧数据后重写（需先启动 Neo4j）
4. **超时中断可恢复** — `build_rag_index.py` 支持断点续跑，再运行一次即可
5. **RAG 验证** — 最后一步验证向量索引是否正确写入了新股票数据

### 快速一键版

```bash
CODE=601211 NAME=国泰君安
cd /tmp/cninfo-stock-monitor

# P0-P1: 数据获取
python3 scripts/fetch_history.py $CODE $NAME
python3 scripts/fetch_pdfs.py

# ⚠️ 此处需手动编辑 config/stocks.json 添加新股票

# P2-P6: 数据处理管线
python3 scripts/extract_pdfs.py
python3 scripts/build_rag_index.py
python3 scripts/fetch_akshare.py
python3 scripts/extract_entities.py
python3 scripts/neo4j_graph.py
python3 scripts/generate_wiki.py

# 验证
python3 scripts/rag_query.py "${NAME}2024年主营业务" $CODE

# 提交
git add -A && git commit -m "增加监控股票: ${NAME} (${CODE})" && git push
```

---

## 设计原则

1. **原文为主**: 所有结构化数据（指标/风险/事件）均源自巨潮网 PDF 原文，AKShare 仅做补充
2. **不预测**: 不做股票预测、自动交易、实时行情下单
3. **自驱执行**: 管线流程可一键顺序执行，无需人工介入
4. **增量友好**: 监控脚本持久化时间戳，索引构建支持 checkpoint 断点续跑

---

## 开发状态

| 阶段 | 任务 | 状态 |
|------|------|------|
| P0 | 架构文档 + 股票元数据解析 | ✅ |
| P1 | 公告抓取 + PDF 下载 | ✅ |
| P2 | PDF 文本提取 + Chunk + ChromaDB 向量索引 + RAG | ✅ |
| P3 | AKShare 财务/行情数据接入 | ✅ |
| P4 | Neo4j 知识图谱 | ✅ |
| P5 | 实体抽取（风险/事件/指标） | ✅ |
| P6 | LLM Wiki 研究页生成 | ✅ |

---

## 许可证

[MIT](LICENSE)
