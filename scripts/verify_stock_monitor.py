#!/usr/bin/env python3
"""
验证年报监控脚本是否存在并可直接执行
"""
import subprocess
import sys

# 检查脚本文件是否存在
script_path = "/tmp/cninfo-stock-monitor/scripts/watch_stock_cninfo.py"
if __name__ == "__main__" in sys.argv:
    try:
        # 先运行脚本
        result = subprocess.run([f"python3 {script_path}", "600089", "特变电工"], 
                              capture_output=True, text=True, timeout=30)
        
        # 输出结果
        print(result.stdout)
        print(result.stderr)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"[ERROR] 脚本文件不存在: {script_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 执行失败: {e}")
        sys.exit(1)
