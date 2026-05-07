#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CNINFO 年报/季报/业绩预告监控脚本
监控股票代码，检测是否有新的公告披露
"""

import subprocess
import sys
from datetime import datetime

CODE = "600089"
STOCK_NAME = "特变电工"

def run_cninfo_api():
    """使用 curl 调用 CNINFO 接口获取新公告"""
    try:
        # 构建 curl 命令
        cmd = [
            "curl", "-s", "-L",
            "http://www.cninfo.com.cn/new/newlist.do",
            f"-d", f'stockCode={CODE}&market=&type=notice&pageSize=20',
            "--connect-timeout", "10",
            "--max-time", "30"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def parse_cninfo_html(html):
    """解析 CNINFO 返回的 HTML，提取公告信息"""
    announcements = []
    try:
        # 使用简单的文本处理
        lines = html.split('\n')
        for line in lines:
            if '公告' in line and '发布' in line:
                # 简单解析日期和标题
                date_str = line[:20]
                title = line[100:200] if len(line) > 200 else ""
                if date_str and title:
                    announcements.append({
                        'date': date_str,
                        'title': title
                    })
    except Exception as e:
        print(f"Parse error: {e}", file=sys.stderr)
    return announcements

def main():
    print(f"开始监控 {STOCK_NAME} ({CODE}) 的新公告...", file=sys.stderr)
    
    # 获取 CNINFO 数据
    response = run_cninfo_api()
    print(f"响应: {response[:500]}", file=sys.stderr)
    
    # 解析公告
    if "Error" in response:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 监控结果：%s" % response.strip(), file=sys.stderr)
        return
    
    # 解析 HTML
    announcements = parse_cninfo_html(response)
    
    # 筛选今日发布的最新公告
    if announcements:
        new_count = len(announcements)
        print(f"\n🆕 特变电工 ({CODE}) 发现 {new_count} 条新公告:", file=sys.stderr)
        for a in reversed(announcements):  # 最新的在前
            print(f"  [{a['date']}] {a['title']}", file=sys.stderr)
        # 输出给终端（用于用户终端查看）
        print(f"\n🆕 特变电工 ({CODE}) 发现 {new_count} 条新公告:", file=sys.stderr)
        for a in announcements:  # 新的在前
            print(f"  [{a['date']}] {a['title']}", file=sys.stderr)
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 无新公告", file=sys.stderr)
        print("\n[SILENT]", file=sys.stderr)

if __name__ == "__main__":
    main()
