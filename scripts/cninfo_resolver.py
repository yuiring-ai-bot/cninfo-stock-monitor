import json
import urllib.parse
import urllib.request
from functools import lru_cache

TOP_SEARCH_DETAIL_URL = "http://www.cninfo.com.cn/new/information/topSearch/detailOfQuery"

PLATE_PARAMS = {
    "sse": ("sse", "sh"),
    "szse": ("szse", "sz"),
    "bj": ("bj", "bj"),
}


def infer_plate(stock_code):
    if stock_code.startswith("6"):
        return "sse"
    if stock_code.startswith(("0", "3")):
        return "szse"
    if stock_code.startswith(("4", "8", "9")):
        return "bj"
    return "szse"


def fallback_org_id(stock_code, plate):
    if plate == "sse":
        return f"gssh0{stock_code}"
    if plate == "bj":
        return f"gfbj0{stock_code}"
    return f"gssz0{stock_code}"


def _plate_params(plate):
    return PLATE_PARAMS.get(plate, PLATE_PARAMS["szse"])


def fallback_stock_info(stock_code):
    plate = infer_plate(stock_code)
    column, plate_param = _plate_params(plate)
    return {
        "code": stock_code,
        "name": "",
        "org_id": fallback_org_id(stock_code, plate),
        "plate": plate,
        "column": column,
        "plate_param": plate_param,
        "source": "fallback",
    }


@lru_cache(maxsize=512)
def resolve_stock_info(stock_code):
    """Resolve cninfo stock metadata via the official top-search endpoint."""
    data = urllib.parse.urlencode({
        "keyWord": stock_code,
        "maxSecNum": 10,
        "maxListNum": 0,
    }).encode()
    req = urllib.request.Request(TOP_SEARCH_DETAIL_URL, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json,text/plain,*/*",
        "Origin": "http://www.cninfo.com.cn",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
        "X-Requested-With": "XMLHttpRequest",
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return fallback_stock_info(stock_code)

    candidates = result.get("keyBoardList") or []
    exact = [item for item in candidates if item.get("code") == stock_code]
    a_shares = [item for item in exact if item.get("category") == "A股"]
    item = (a_shares or exact or candidates or [None])[0]
    if not item or not item.get("orgId"):
        return fallback_stock_info(stock_code)

    plate = item.get("plate") or infer_plate(stock_code)
    column, plate_param = _plate_params(plate)
    return {
        "code": item.get("code") or stock_code,
        "name": item.get("zwjc") or "",
        "org_id": item["orgId"],
        "plate": plate,
        "column": column,
        "plate_param": plate_param,
        "source": "topSearch/detailOfQuery",
    }


def build_org_id(stock_code):
    return resolve_stock_info(stock_code)["org_id"]


def get_exchange(stock_code):
    return resolve_stock_info(stock_code)["column"]
