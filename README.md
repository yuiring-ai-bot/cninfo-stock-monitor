# 巨潮股票公告与财报监控工具

这是一个面向巨潮资讯网可查询股票的自动化监控工具，用于定时获取指定股票的年报、季报、半年报、业绩预告/快报等公告信息。仓库中的 `600089` 和“特变电工”仅作为示例股票与样例数据存在，不代表项目只服务于该股票。

## 项目概览

- **适用范围**: 巨潮资讯网可查询的 A 股股票
- **示例股票代码**: 600089
- **示例股票名称**: 特变电工
- **示例交易所**: 上交所 (SSE)
- **示例 Org ID**: `gssh0600089`

## 项目结构

```text
├── 600089_history/               # 示例股票历史数据
│   ├── _summary.json             # 数据摘要
│   ├── annual.json               # 年度报告数据
│   ├── semi_5y.json              # 近 5 年半年报数据
│   ├── quarterly_5y.json         # 近 5 年季报数据
│   └── all_2y.json               # 近 2 年公告数据
├── scripts/                      # 监控脚本
│   ├── watch_stock_cninfo.py     # 巨潮网监控脚本
│   ├── onboard_stock.py          # 新股票录入脚本
│   ├── watch_stock.py            # 通用监控脚本
│   └── watch_stock_em.py         # 东方财富监控脚本
├── config/
│   └── stocks.json               # 批量监控股票配置
├── 600089_last_check.json        # 示例股票最近检查状态
├── 600089_last_check_em.json     # 示例股票东方财富检查状态
└── README.md
```

## 功能特点

1. **通用股票监控**: 通过股票代码和股票名称参数监控任意支持的股票。
2. **公告类型覆盖**: 支持年报、季报、半年报、业绩预告/快报等公告类型。
3. **历史数据录入**: 可抓取并保存指定股票的历史公告数据。
4. **多数据源支持**: 支持巨潮网 API，并提供东方财富脚本作为补充数据源。
5. **状态持久化**: 自动保存最近检查状态，便于定时任务增量监控。

## 技术栈

- **Python 3.x**
- **巨潮网 API**: 主要数据源
- **东方财富 API**: 补充数据源
- **JSON**: 本地数据存储格式
- **GitHub Actions / cron**: 可用于定时监控调度

## 监控指标

### 年报相关

- 年度报告全文 (`category_ndbg_szsh`)
- 年度报告摘要 (`category_ndbg_szsh`)
- 审计报告 (`category_ndbg_szsh`)

### 季报相关

- 一季度报告 (`category_jjdbg_szsh`)
- 三季度报告 (`category_jjdbg_szsh`)

### 业绩预告

- 业绩预告/快报 (`category_yjygjxz`)
- 业绩快报 (`category_yjkb`)

### 其他重要公告

- 重大事项 (`category_gddz`)
- 董事会决议 (`category_dshjys`)
- 股东大会决议 (`category_gzhys`)
- 利润分配预案 (`category_ndbg_szsh`)

## 使用方法

### 1. 监控单只股票

```bash
python scripts/watch_stock_cninfo.py 600089 特变电工
```

将 `600089 特变电工` 替换为需要监控的股票代码和名称即可。

### 2. 录入股票历史数据

```bash
python scripts/onboard_stock.py 600089 特变电工
```

### 3. 设置定时监控

```bash
# 每 30 分钟检查一次示例股票
*/30 * * * * cd /path/to/project && python scripts/watch_stock_cninfo.py 600089 特变电工
```

如需监控多只股票，可以为每只股票配置一条定时任务，或在调度脚本中循环调用监控脚本。

### 4. 配置每日摘要监控列表

每日摘要脚本从 `config/stocks.json` 读取监控股票，不在脚本中硬编码股票列表：

```json
{
  "stocks": [
    { "code": "600089", "name": "特变电工" },
    { "code": "600927", "name": "永安期货" }
  ]
}
```

运行默认配置：

```bash
python scripts/daily_summary.py
```

也可以通过命令行参数或环境变量指定其他配置文件：

```bash
python scripts/daily_summary.py /path/to/stocks.json
CNINFO_STOCK_CONFIG=/path/to/stocks.json python scripts/daily_summary.py
```

## API 说明

### 巨潮网 API

- **URL**: `http://www.cninfo.com.cn/new/hisAnnouncement/query`
- **参数**:
  - `stock`: 股票代码,orgId，例如 `600089,gssh0600089`
  - `tabName`: `fulltext`
  - `category`: 公告类型代码
  - `pageSize`: 每页数量
  - `pageNum`: 页码

### Org ID 获取规则

脚本会优先调用巨潮搜索接口反查股票元数据：

- **URL**: `http://www.cninfo.com.cn/new/information/topSearch/detailOfQuery`
- **关键参数**: `keyWord={stock_code}`
- **使用字段**: `keyBoardList[].code`、`orgId`、`plate`、`zwjc`

这样可以覆盖非标准 `orgId` 的股票，例如：

| 股票代码 | 股票名称 | 巨潮返回的 Org ID |
| --- | --- | --- |
| 600927 | 永安期货 | `gfbj0833840` |
| 601186 | 中国铁建 | `9900004347` |

当前缀规则只作为搜索接口不可用时的兜底。

### 兜底前缀规则

| 股票代码前缀 | 交易所 | Org ID 格式 | 示例 |
| --- | --- | --- | --- |
| 6 | 上交所 | `gssh0` + 6 位代码 | `600089` -> `gssh0600089` |
| 0, 3 | 深交所 | `gssz0` + 6 位代码 | `000001` -> `gssz0000001` |
| 4, 8, 9 | 北交所 | `gfbj0` + 6 位代码 | `830799` -> `gfbj0830799` |

## 数据格式

### 状态文件 (`{stock_code}_last_check.json`)

```json
{
  "last_announcement_time": 1777564800000,
  "last_check_time": 1778081551263,
  "total_tracked": 58,
  "stock_code": "600089",
  "stock_name": "特变电工",
  "exchange": "sse",
  "org_id": "gssh0600089"
}
```

### 数据摘要 (`{stock_code}_history/_summary.json`)

```json
{
  "stock_code": "600089",
  "stock_name": "特变电工",
  "onboard_time": "2026-05-06T08:43:49.110390",
  "total_annual": 0,
  "total_semi_5y": 0,
  "total_quarterly_5y": 0,
  "total_all_2y": 0,
  "annual_years": []
}
```

## 通知功能

项目可以接入多种通知方式：

1. **GitHub Actions 通知**: 通过工作流自动发送通知。
2. **Webhook 推送**: 支持自定义 Webhook 推送。
3. **邮件通知**: 可通过 SMTP 发送邮件通知。
4. **即时消息**: 可扩展微信、钉钉等即时通讯工具。

## 计划任务

建议的监控频率：

- **高频监控**: 每 30 分钟检查一次，适合财报披露期。
- **常规监控**: 每 1 小时检查一次，适合正常时期。
- **低频监控**: 每天检查一次，适合非交易日。

## 开发计划

- [ ] 添加更多数据源支持
- [ ] 实现数据可视化界面
- [ ] 添加 PDF 报告自动下载
- [ ] 实现金融指标自动计算
- [ ] 添加多股票批量监控
- [ ] 实现移动端推送通知

## 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进本项目。

## 联系

如有问题或建议，请通过 GitHub Issues 联系。
