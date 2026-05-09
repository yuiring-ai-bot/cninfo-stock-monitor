# 证券研究知识库架构文档

> Version 1.0 | 2026-05-08 | 基于 cninfo-stock-monitor 构建

## 系统定位

**目标**：证券研究资料整理系统，形成"原文可追溯、指标可查询、事件可关联、结论可复盘"的知识库。

**不做的**：股票预测、自动交易、实时行情下单

## 数据源分工

| 数据源 | 角色 | 内容 |
|--------|------|------|
| 巨潮网抓取器 | **核心证据源** | 年报/半年报/季报/临时公告元数据 + PDF 原文 |
| AKShare | 补充数据源 | 行情、市值、行业分类、财务指标、分红等结构化数据 |
| Neo4j | 关系图谱 | 公司-公告-指标-风险-事件 的关系网络 |
| LLM Wiki | 人类可读研究页 | 公司研究页、年报分析页、风险页、事件页 |

## 现有代码资产

```
/tmp/cninfo-stock-monitor/
├── scripts/
│   ├── cninfo_resolver.py      # 股票元数据解析（orgId 查询，LRU 缓存）
│   ├── watch_stock_cninfo.py   # 单股实时监控（增量）
│   ├── watch_stock.py          # 全市场类别筛选监控
│   ├── watch_stock_em.py       # 东方财富 API 监控
│   ├── fetch_history.py        # 历史数据抓取（6类：年报/半年报/季报/业绩预告/全公告/index）
│   ├── onboard_stock.py        # 新股录入（4类数据）
│   ├── daily_summary.py        # 多股每日摘要（读取 config/stocks.json）
│   ├── cninfo_pdfs.py          # PDF 下载器（读取 history 输出）
│   └── fetch_pdfs.py           # PDF 下载命令行包装
├── config/
│   └── stocks.json             # 批量监控股票配置
└── docs/
    └── ARCHITECTURE.md
```

## 输出数据目录

运行数据目录由 `CNINFO_DATA_DIR` 控制。未设置时，Linux/macOS 默认 `/tmp/cninfo_watch`，Windows 默认系统临时目录下的 `cninfo_watch`。

```
/tmp/cninfo_watch/
├── {code}_last_check.json          # 监控状态（增量时间戳）
├── {code}_last_check_em.json       # 东方财富监控状态
├── {code}_history/                 # onboard_stock.py 输出（旧格式）
│   ├── annual.json / semi_5y.json / quarterly_5y.json / all_2y.json
│   └── _summary.json
└── history/                        # fetch_history.py 输出（新格式）
    └── {code}/
        ├── annual_reports_all_history.json   # 全部历史年报
        ├── half_reports_5years.json          # 近5年半年报
        ├── quarter_reports_5years.json       # 近5年季报
        ├── forecast_reports_5years.json      # 近5年业绩预告
        ├── all_announcements_2years.json     # 近2年全公告
        └── index.json                        # 索引汇总
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

## 公告类别代码对照

| category | 说明 | 对应 Filing Type |
|----------|------|-----------------|
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
| `/new/hisAnnouncement/query` | POST | 公告列表查询（年报/季报/业绩预告） |
| `/new/announcement/showDownloadScreen` | GET | PDF 下载 |

### 东方财富

| 端点 | 方法 | 用途 |
|------|------|------|
| `http://np-anotice-stock.eastmoney.com/api/security/ann` | POST | 全公告查询 |

## Neo4j 图谱规划

### 节点类型

```
Company      - 上市公司
Filing       - 公告/报告（含年报/半年报/季报/临时公告）
Metric       - 财务指标
Risk         - 风险事件
Event        - 重大事项
Industry     - 行业
Chunk        - PDF 原文切片（RAG 用）
```

### 关系类型

```
(Company)-[:FILES]->(Filing)
(Filing)-[:DISCLOSES]->(Metric)
(Filing)-[:MENTIONS]->(Risk)
(Filing)-[:DISCLOSES_EVENT]->(Event)
(Company)-[:BELONGS_TO]->(Industry)
(Event)-[:AFFECTS]->(Company)
(Chunk)-[:SUPPORTS]->(Risk)
(Chunk)-[:SUPPORTS]->(Event)
```

## 开发任务清单

| 阶段 | 任务 | 优先级 | 状态 |
|------|------|--------|------|
| P0 | 梳理现有抓取器，输出架构文档 | — | 🔄 进行中 |
| P1 | 统一公告元数据，输出 filing 表 | — | ⏳ 待开始 |
| P0 | 新增：PDF 下载器 | P0 | ⏳ 待开始 |
| P2 | PDF 解析 + chunk + 向量索引 + RAG | P1 | ⏳ 待开始 |
| P3 | 接入 AKShare | P2 | ⏳ 暂缓 |
| P4 | 抽取 Risk/Event/Metric | P2 | ⏳ 待开始 |
| P5 | 写入 Neo4j 图谱 | P2 | ⏳ 待开始 |
| P6 | 生成 LLM Wiki 研究页 | P2 | ⏳ 待开始 |

## Wiki 目录结构

```
/opt/data/home/wiki/finance/
├── index.md                    # 入口页
├── schema.md                   # 规范定义
├── log.md                      # 操作日志
├── companies/                  # 公司实体页
│   ├── 600089-tebian-electric.md
│   ├── 600790-qingfangcheng.md
│   └── ...
├── concepts/                   # 概念/方法论
│   └── cninfo-api-usage.md
└── comparisons/                # 对比/汇总
    └── sse-monitored-stocks.md
```

## 技术栈

- **PDF 解析**: PyMuPDF (fitz)
- **向量数据库**: 待选（FAISS / ChromaDB / Qdrant）
- **Embedding**: 待定（bge / text2vec / OpenAI）
- **图数据库**: Neo4j 5.18.0（已安装）
- **LLM**: 用户配置
- **语言**: Python 3.13

## 已知限制

- 巨潮网历史年报最早到 2011 年左右
- 部分股票 orgId 非标准格式（期货公司、央企），需搜索 API 解析
- PDF 下载需处理反爬和超时
- AKShare 第一阶段不强依赖，可后置
