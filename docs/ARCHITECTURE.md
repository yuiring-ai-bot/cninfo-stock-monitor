# 证券研究知识库架构文档

> Version 2.0 | 2026-05-09 | MVP 完成

## 系统定位

**目标**：证券研究资料整理系统，形成"原文可追溯、指标可查询、事件可关联、结论可复盘"的知识库。

**不做的**：股票预测、自动交易、实时行情下单

## 数据源分工

| 数据源 | 角色 | 内容 |
|--------|------|------|
| 巨潮网抓取器 | **核心证据源** | 年报/半年报/季报/临时公告元数据 + PDF 原文 |
| AKShare | 补充数据源 | 行情、市值、行业分类、财务指标、分红等结构化数据 |
| ChromaDB | 向量检索引擎 | PDF原文切片语义嵌入（all-MiniLM-L6-v2 ONNX），支持 RAG 问答 |
| Neo4j | 关系图谱 | 公司-公告-指标-风险-事件 的关系网络 |
| LLM Wiki | 人类可读研究页 | 公司研究页、年报分析页、风险页、事件页 |

## 管线流程

```
巨潮网 API ──→ fetch_history.py ──→ watch_stock_cninfo.py ──→ fetch_pdfs.py
                                                                     │
                                                                     ▼
                                                              extract_pdfs.py
                                                              (PyMuPDF → JSON)
                                                                     │
                                                            ┌────────┴────────┐
                                                            ▼                 ▼
                                                    build_rag_index.py    extract_entities.py
                                                    (ChromaDB向量索引)    (规则引擎抽取)
                                                            │                 │
                                                            ▼                 ▼
                                                     rag_query.py       neo4j_graph.py
                                                     (RAG问答)          (Neo4j图谱)
                                                                           │
                                                                           ▼
                                                                    generate_wiki.py
                                                                    (LLM Wiki页)
                                                                           │
                                                                           ▼
                                                                    fetch_akshare.py
                                                                    (补充结构化数据)
```

高频路径与模型路径强制解耦：`poll_announcements.py` 只拉取公告元数据并写 JSON，不调用模型；RAG/Wiki/LLM 类任务只能读取已产出的数据，由手动 workflow 或离线脚本显式触发。无新增公告时不得调用模型。

必要模型调用必须统一经过 `model_gateway.py`。该入口负责先执行确定性 gating（例如无新增公告、空 payload、无候选内容直接退出），再调用具体 provider。禁止在高频拉取、PDF 下载、索引构建等脚本中直接调用外部模型。

## 代码资产

```
/tmp/cninfo-stock-monitor/
├── scripts/
│   ├── cninfo_resolver.py         # 股票元数据解析（orgId 查询，LRU 缓存）
│   ├── watch_stock_cninfo.py      # 单股实时监控（增量）
│   ├── watch_stock.py             # 全市场类别筛选监控
│   ├── watch_stock_em.py          # 东方财富 API 监控
│   ├── fetch_history.py           # 历史数据抓取（6类：年报/半年报/季报/业绩预告/全公告/index）
│   ├── onboard_stock.py           # 新股录入（4类数据）
│   ├── daily_summary.py           # 多股每日摘要（读取 config/stocks.json）
│   ├── poll_announcements.py      # 高频公告轮询（不调用模型）
│   ├── model_gateway.py           # 统一模型调用入口（带确定性 gating）
│   ├── cninfo_pdfs.py             # PDF 下载引擎
│   ├── fetch_pdfs.py              # PDF 下载命令行包装
│   │
│   ├── extract_pdfs.py            # [P2] 批量PDF文本提取 (PyMuPDF → JSON)
│   ├── build_rag_index.py         # [P2] 文本切分 + ChromaDB向量索引（增量构建）
│   ├── rag_query.py               # [P2] RAG语义问答接口
│   ├── fetch_akshare.py           # [P3] AKShare财务指标/日线行情/基础信息
│   ├── neo4j_graph.py             # [P4] Neo4j图谱写入
│   ├── extract_entities.py        # [P5] 规则引擎实体抽取（风险/事件/指标）
│   └── generate_wiki.py           # [P6] LLM Wiki研究页生成
├── config/
│   └── stocks.json                # 批量监控股票配置
└── docs/
    └── ARCHITECTURE.md
```

## 输出数据目录

运行数据目录由 `CNINFO_DATA_DIR` 控制。未设置时，Linux/macOS 默认 `/tmp/cninfo_watch`。

```
/tmp/cninfo_watch/
├── pdfs/                          # PDF原始文件
│   ├── 600089_xxx.pdf
│   └── ...
├── texts/                         # 结构化文本JSON（extract_pdfs.py输出）
│   ├── {filing_id}.json           # {pages[], metadata}
│   └── ...
├── chunks/                        # 切分元数据索引
│   └── chunk_index.json           # 总chunk数/文件数/生成时间
├── chromadb/                      # ChromaDB持久化存储
│   └── ...                        # 47,766 向量 (all-MiniLM-L6-v2)
├── akshare/                       # AKShare结构化数据
│   └── stock_{code}.json
├── entities/                      # 实体抽取结果JSON
│   ├── risks_{filing_id}.json
│   ├── events_{filing_id}.json
│   └── metrics_{filing_id}.json
├── outputs/
│   └── wiki/                      # LLM Wiki研究页
│       ├── index.md               # 入口页
│       ├── companies/             # 公司研究页
│       └── ...
├── filings/
│   └── filing_index.json          # 统一公告索引
├── history/                       # 历史公告数据（旧格式）
│   └── {code}/
│       └── ...
└── {code}_last_check.json         # 监控状态（增量时间戳）
```

## 公告元数据字段规范

```json
{
  "announcementId":    "string,  巨潮公告唯一ID",
  "secCode":           "string,  股票代码",
  "secName":           "string,  股票名称",
  "orgId":             "string,  巨潮机构ID",
  "announcementTitle": "string,  公告标题",
  "announcementTime":  "int,     发布时间戳(ms)",
  "publishDate":       "string,  格式化日期 YYYY-MM-DD",
  "adjunctUrl":        "string,  PDF附件相对路径",
  "adjunctSize":       "int,     附件大小(KB)",
  "adjunctType":       "string,  附件类型(通常PDF)",
  "columnId":          "string,  栏目ID",
  "announcementType":  "string,  公告类型编码"
}
```

## 向量索引 (ChromaDB)

| 属性 | 值 |
|------|-----|
| 模型 | all-MiniLM-L6-v2 (ONNX, ChromaDB内置) |
| Collection | `cninfo_chunks` |
| Chunk数 | 47,766 |
| 向量维度 | 384 |
| 距离度量 | cosine |
| Chunk策略 | 800字符窗口, 100字符重叠 |
| 增量策略 | checkpoint文件 `build_checkpoint.json`, 逐文件处理 |

### Metadata schema

```json
{
  "filing_id":     "巨潮公告唯一ID",
  "stock_code":    "股票代码 (e.g. 600089)",
  "page_num":      "PDF页码",
  "title":         "公告标题",
  "publish_date":  "发布日期 YYYY-MM-DD",
  "type":          "公告类型 (annual_report/semi_annual_report/temporary_announcement)",
  "char_count":    "chunk字符数"
}
```

## Neo4j 图谱

### 节点

| 标签 | 说明 | 数量 |
|------|------|------|
| `Company` | 上市公司 | 5 |
| `Filing` | 公告/报告 | 336 |
| `Risk` | 风险（关联50+） | 2,404 |
| `Event` | 重大事项（关联5+） | 4,871 |
| `Metric` | 财务指标 | 10 |

### 关系

```
(Company)-[:FILES]->(Filing)
(Company)-[:HAS_RISK]->(Risk)
(Filing)-[:MENTIONS]->(Risk)
(Filing)-[:DISCLOSES_EVENT]->(Event)
(Filing)-[:DISCLOSES]->(Metric)
(Company)-[:HAS_EVENT]->(Event)
```

## 公告类别代码对照

| category | 说明 | filing_type |
|----------|------|-------------|
| `category_ndbg_szsh` | 年度报告 | `annual_report` |
| `category_bndbg_szsh` | 半年度报告 | `semi_annual_report` |
| `category_jdbg_szsh` / `category_jjdbg_szsh` | 季度报告 | `quarterly_report` |
| `category_yjygjxz` | 业绩预告/快报 | `earnings_forecast` |
| 其他18类 | 临时公告 | `temporary_announcement` |

## API 端点

### 巨潮网

| 端点 | 方法 | 用途 |
|------|------|------|
| `/new/information/topSearch/detailOfQuery` | POST | 股票元数据查询（orgId, plate） |
| `/new/hisAnnouncement/query` | POST | 公告列表查询 |
| `/new/announcement/showDownloadScreen` | GET | PDF 下载 |

### 东方财富

| 端点 | 方法 | 用途 |
|------|------|------|
| `http://np-anotice-stock.eastmoney.com/api/security/ann` | POST | 全公告查询 |

## 调度边界

- `poll-announcements.yml`: 每 5 分钟运行，只拉取巨潮公告元数据、更新状态并上传 JSON artifact。
- `model-analysis.yml`: 仅手动触发，并且只能调用 `model_gateway.py`。

模型调用不能放进高频轮询任务。分析任务必须显式读取某次轮询产物或其他人工指定输入；当轮询结果没有新增公告时，`model_gateway.py` 必须在 provider 调用前退出。

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| PDF解析 | PyMuPDF (fitz) | — |
| 向量数据库 | ChromaDB | — |
| Embedding | all-MiniLM-L6-v2 (ONNX) | — |
| 图数据库 | Neo4j | 5.18.0+ |
| 结构化数据 | AKShare | — |
| 语言 | Python | 3.13 |

## 已知限制

- 巨潮网历史年报最早到 2011 年左右
- 部分股票 orgId 非标准格式（期货公司、央企），需搜索 API 解析
- PDF 下载需处理反爬和超时
- 非标准股票（如600927/601186）的公告元数据可能缺失标题和日期（filing_index 无此信息）
