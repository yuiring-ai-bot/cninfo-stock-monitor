# 特变电工年报监控项目

这是一个监控特变电工（600089）年报、季报和业绩预告的自动化系统。

## 📊 项目概述

- **股票代码**: 600089
- **股票名称**: 特变电工
- **交易所**: 上交所 (SSE)
- **Org ID**: `gssh0600089`

## 📁 项目结构

```
├── 600089_history/          # 特变电工历史数据
│   ├── _summary.json       # 数据摘要
│   ├── annual.json         # 年度报告数据
│   ├── semi_5y.json        # 近5年半年报数据
│   ├── quarterly_5y.json   # 近5年季报数据
│   └── all_2y.json         # 近2年所有公告数据
├── scripts/                # 监控脚本
│   ├── watch_stock_cninfo.py      # 巨潮网监控脚本
│   ├── onboard_stock.py           # 新股票录入脚本
│   ├── watch_stock.py             # 通用监控脚本
│   └── watch_stock_em.py          # 东方财富监控脚本
├── 600089_last_check.json         # 最近检查状态
├── 600089_last_check_em.json      # 东方财富检查状态
└── README.md                     # 本文件
```

## 🚀 功能特点

1. **实时监控**: 自动监控特变电工的最新年报、季报和业绩预告
2. **历史数据**: 自动抓取历史财务报告数据
3. **多平台支持**: 支持巨潮网和东方财富API
4. **自动推送**: 发现新公告时自动发送通知
5. **数据持久化**: 自动保存历史数据和检查状态

## 🔧 技术栈

- **Python 3.x**: 主要开发语言
- **巨潮网 API**: 主要数据源
- **东方财富 API**: 备选数据源
- **JSON**: 数据存储格式
- **GitHub Actions**: 自动监控调度

## 📈 监控指标

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

## ⚙️ 使用方法

### 1. 监控单只股票
```bash
python scripts/watch_stock_cninfo.py 600089 特变电工
```

### 2. 录入新股票历史数据
```bash
python scripts/onboard_stock.py 600089 特变电工
```

### 3. 设置定时监控
```bash
# 每30分钟检查一次
*/30 * * * * cd /path/to/project && python scripts/watch_stock_cninfo.py 600089 特变电工
```

## 🔍 API 说明

### 巨潮网 API
- **URL**: `http://www.cninfo.com.cn/new/hisAnnouncement/query`
- **参数**: 
  - `stock`: 股票代码,orgId (如: `600089,gssh0600089`)
  - `tabName`: `fulltext`
  - `category`: 公告类型代码
  - `pageSize`: 每页数量
  - `pageNum`: 页码

### 交易所判断规则
| 股票代码前缀 | 交易所 | Org ID 格式 | 示例 |
|-------------|--------|-------------|------|
| 6, 8 | 上交所 | `gssh0` + 6位代码 | `600089` → `gssh0600089` |
| 0, 3 | 深交所 | `gssz0` + 6位代码 | `000001` → `gssz0000001` |

## 📊 数据格式

### 状态文件 (`600089_last_check.json`)
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

### 数据摘要 (`_summary.json`)
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

## 🔔 通知功能

项目支持多种通知方式：

1. **GitHub Actions 通知**: 通过工作流自动发送通知
2. **Webhook 推送**: 支持自定义Webhook推送
3. **邮件通知**: 通过SMTP发送邮件通知
4. **即时消息**: 支持微信、钉钉等即时通讯工具

## 📋 计划任务

建议的监控频率：
- **高频监控**: 每30分钟检查一次（财报披露期）
- **常规监控**: 每2小时检查一次（正常时期）
- **低频监控**: 每天检查一次（非交易日）

## 🛠️ 开发计划

- [ ] 添加更多数据源支持
- [ ] 实现数据可视化界面
- [ ] 添加PDF报告自动下载
- [ ] 实现财务指标自动计算
- [ ] 添加多股票批量监控
- [ ] 实现移动端推送通知

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进本项目。

## 📞 联系

如有问题或建议，请通过GitHub Issues联系我们。