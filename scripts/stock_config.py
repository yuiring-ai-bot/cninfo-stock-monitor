import json
import os

from cninfo_resolver import resolve_stock_info

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_STOCK_CONFIG = os.path.join(PROJECT_ROOT, "config", "stocks.json")


def load_stocks(config_path=None):
    path = config_path or os.environ.get("CNINFO_STOCK_CONFIG") or DEFAULT_STOCK_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    stocks = config.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        raise ValueError(f"{path} must contain a non-empty 'stocks' list")

    normalized = []
    for index, stock in enumerate(stocks, start=1):
        code = str(stock.get("code", "")).strip()
        if not code:
            raise ValueError(f"{path} stocks[{index}] is missing code")
        name = str(stock.get("name", "")).strip()
        if not name:
            name = resolve_stock_info(code).get("name") or code
        normalized.append({"code": code, "name": name})
    return normalized
