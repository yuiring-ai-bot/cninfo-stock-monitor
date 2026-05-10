#!/usr/bin/env python3
"""
Fetch supplemental AKShare data for stocks in config/stocks.json.

Default behavior is incremental: existing JSON files are loaded and only
configured stocks missing from those files are fetched. Use --refresh to
refresh all configured stocks.
"""
import argparse
import json
import os

from cninfo_paths import DATA_DIR
from stock_config import load_stocks

STRUCTURED_DIR = os.path.join(DATA_DIR, "structured")
os.makedirs(STRUCTURED_DIR, exist_ok=True)


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def get_stock_codes():
    return [stock["code"] for stock in load_stocks()]


def select_codes(existing, refresh=False):
    codes = get_stock_codes()
    if refresh:
        return codes
    return [code for code in codes if code not in existing]


def get_stock_info_akshare(refresh=False):
    try:
        import akshare as ak
    except ImportError:
        print("akshare is not installed")
        return {}

    path = os.path.join(STRUCTURED_DIR, "stock_info.json")
    results = load_json(path)
    target_codes = select_codes(results, refresh)
    if not target_codes:
        print("  stock_info.json already covers configured stocks")
        return results

    for code in target_codes:
        try:
            df = ak.stock_individual_info_em(symbol=code)
            info = df.set_index(df.columns[0])[df.columns[1]].to_dict()
            results[code] = {str(k): str(v) for k, v in info.items()}
            print(f"  ok {code}: stock info")
        except Exception as exc:
            print(f"  warn {code}: {exc}")
            results[code] = {"error": str(exc)}

    save_json(path, results)
    return results


def get_financial_indicators(refresh=False):
    try:
        import akshare as ak
    except ImportError:
        print("akshare is not installed")
        return {}

    path = os.path.join(STRUCTURED_DIR, "financial_indicators.json")
    results = load_json(path)
    target_codes = select_codes(results, refresh)
    if not target_codes:
        print("  financial_indicators.json already covers configured stocks")
        return results

    for code in target_codes:
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
            if len(df) > 0:
                results[code] = {str(k): str(v) for k, v in df.iloc[0].to_dict().items()}
                print(f"  ok {code}: financial indicators")
            else:
                results[code] = {"error": "empty response"}
        except Exception as exc:
            print(f"  warn {code}: {exc}")
            results[code] = {"error": str(exc)}

    save_json(path, results)
    return results


def get_market_data(refresh=False):
    try:
        import akshare as ak
    except ImportError:
        print("akshare is not installed")
        return {}

    market_path = os.path.join(STRUCTURED_DIR, "market_data.json")
    market = load_json(market_path)
    target_codes = select_codes(market, refresh)

    if target_codes:
        spot_df = ak.stock_zh_a_spot_em()
        for code in target_codes:
            try:
                stock_df = spot_df[spot_df["代码"] == code]
                if len(stock_df) > 0:
                    market[code] = {str(k): str(v) for k, v in stock_df.iloc[0].to_dict().items()}
                    print(f"  ok {code}: market data")
                else:
                    market[code] = {"error": "not found in spot data"}
                    print(f"  warn {code}: not found in spot data")
            except Exception as exc:
                print(f"  warn {code}: {exc}")
                market[code] = {"error": str(exc)}
        save_json(market_path, market)
    else:
        print("  market_data.json already covers configured stocks")

    history_path = os.path.join(STRUCTURED_DIR, "daily_history.json")
    history = load_json(history_path)
    history_codes = select_codes(history, refresh)
    if history_codes:
        for code in history_codes:
            try:
                df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                df = df.tail(60)
                history[code] = json.loads(df.to_json(orient="records", force_ascii=False))
                print(f"  ok {code}: daily history {len(df)} rows")
            except Exception as exc:
                print(f"  warn {code}: {exc}")
                history[code] = {"error": str(exc)}
        save_json(history_path, history)
    else:
        print("  daily_history.json already covers configured stocks")

    return market


def main():
    parser = argparse.ArgumentParser(description="Fetch AKShare data for configured stocks")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="refresh all configured stocks instead of fetching only missing stocks",
    )
    args = parser.parse_args()

    stock_codes = get_stock_codes()
    print("=" * 50)
    print("P3: AKShare supplemental data")
    print("=" * 50)

    print("\n1. Stock info")
    info = get_stock_info_akshare(refresh=args.refresh)

    print("\n2. Financial indicators")
    fins = get_financial_indicators(refresh=args.refresh)

    print("\n3. Market data")
    mkt = get_market_data(refresh=args.refresh)

    print(f"\n{'=' * 50}")
    print("AKShare data fetch complete")
    print(f"  stock info: {len(info)}/{len(stock_codes)}")
    print(f"  financial indicators: {len(fins)}/{len(stock_codes)}")
    print(f"  market data: {len(mkt)}/{len(stock_codes)}")
    print(f"  data dir: {STRUCTURED_DIR}")


if __name__ == "__main__":
    main()
