#!/usr/bin/env python3
"""
备份特变电工(600089)股票监控脚本的旧版本
"""
import os
import sys

# 备份现有脚本
current_script = "/tmp/cninfo-stock-monitor/scripts/watch_stock_cninfo.py"
if os.path.exists(current_script):
    with open(current_script, 'r') as f:
        original_content = f.read()
    
    # 保存备份
    backup_path = "/tmp/cninfo-stock-monitor/backup_watch_stock_cninfo.py"
    with open(backup_path, 'w') as f:
        f.write(original_content)
    
    print(f"已备份原脚本到：{backup_path}")
    print(f"原脚本大小：{os.path.getsize(current_script)} 字节")

print("备份已完成")
sys.exit(0)
