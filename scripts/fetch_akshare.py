#!/usr/bin/env python3
"""
P3: AKShare接入 — 补充股票基础信息/行业分类/财务指标/行情
"""
import json
import os
import sys

from cninfo_paths import DATA_DIR
from stock_config import load_stocks

STRUCTURED_DIR = os.path.join(DATA_DIR, "structured")
os.makedirs(STRUCTURED_DIR, exist_ok=True)

def get_stock_codes():
    return [stock["code"] for stock in load_stocks()]

def get_stock_info_akshare():
    """获取股票基础信息（行业分类、主营业务等）"""
    try:
        import akshare as ak
    except ImportError:
        print("❌ akshare 未安装")
        return {}
    
    info_path = os.path.join(STRUCTURED_DIR, "stock_info.json")
    if os.path.exists(info_path):
        with open(info_path) as f:
            return json.load(f)
    
    results = {}
    for code in get_stock_codes():
        try:
            # 股票基本信息
            df = ak.stock_individual_info_em(symbol=code)
            info = df.set_index(df.columns[0])[df.columns[1]].to_dict()
            results[code] = info
            print(f"  ✅ {code}: {info.get('股票简称','?')}")
        except Exception as e:
            print(f"  ⚠️ {code}: {e}")
            results[code] = {"error": str(e)}
    
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def get_financial_indicators():
    """获取核心财务指标"""
    try:
        import akshare as ak
    except ImportError:
        return {}
    
    fins_path = os.path.join(STRUCTURED_DIR, "financial_indicators.json")
    if os.path.exists(fins_path):
        with open(fins_path) as f:
            return json.load(f)
    
    results = {}
    for code in get_stock_codes():
        try:
            # 财务指标
            df = ak.stock_financial_abstract_ths(symbol=code)
            # 取最近一期
            if len(df) > 0:
                latest = df.iloc[0].to_dict()
                results[code] = {k: str(v) for k, v in latest.items()}
                print(f"  ✅ {code}: 财务指标获取成功")
        except Exception as e:
            print(f"  ⚠️ {code} 财务指标: {e}")
    
    with open(fins_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def get_market_data():
    """获取行情/市值数据"""
    try:
        import akshare as ak
    except ImportError:
        return {}
    
    mkt_path = os.path.join(STRUCTURED_DIR, "market_data.json")
    if os.path.exists(mkt_path):
        with open(mkt_path) as f:
            return json.load(f)
    
    results = {}
    for code in get_stock_codes():
        try:
            # 实时行情
            df = ak.stock_zh_a_spot_em()
            stock_df = df[df["代码"] == code]
            if len(stock_df) > 0:
                row = stock_df.iloc[0].to_dict()
                results[code] = {k: str(v) for k, v in row.items()}
                print(f"  ✅ {code}: 市值 {row.get('总市值','?')}")
            else:
                print(f"  ⚠️ {code}: 未找到行情")
        except Exception as e:
            print(f"  ⚠️ {code} 行情: {e}")
    
    # 历史日线
    hist_path = os.path.join(STRUCTURED_DIR, "daily_history.json")
    if not os.path.exists(hist_path):
        hist_data = {}
        for code in get_stock_codes():
            try:
                # 过去60个交易日
                df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                df = df.tail(60)
                hist_data[code] = json.loads(df.to_json(orient="records", force_ascii=False))
                print(f"  ✅ {code}: 日线数据 {len(df)} 条")
            except Exception as e:
                print(f"  ⚠️ {code} 日线: {e}")
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(hist_data, f, ensure_ascii=False, indent=2)
    
    with open(mkt_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def main():
    stock_codes = get_stock_codes()
    print("=" * 50)
    print("📊 P3: AKShare 数据补充")
    print("=" * 50)
    
    print("\n1️⃣ 股票基础信息...")
    info = get_stock_info_akshare()
    
    print("\n2️⃣ 财务指标...")
    fins = get_financial_indicators()
    
    print("\n3️⃣ 行情数据...")
    mkt = get_market_data()
    
    print(f"\n{'='*50}")
    print("📊 AKShare 数据补充完成！")
    print(f"  股票信息: {len(info)}/{len(stock_codes)}")
    print(f"  财务指标: {len(fins)}/{len(stock_codes)}")
    print(f"  行情数据: {len(mkt)}/{len(stock_codes)}")
    print(f"  数据目录: {STRUCTURED_DIR}")

if __name__ == "__main__":
    main()
