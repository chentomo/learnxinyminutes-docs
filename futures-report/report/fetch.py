"""從證交所（TWSE）與期交所（TAIFEX）抓取盤後公開資料。

每個 fetch_* 函式都回傳已解析好的 Python 結構；查無資料（休市、尚未公布）時回傳 None。
期交所的下載端點回傳 Big5 (cp950) 編碼的 CSV，欄位以中文表頭辨識，避免依賴欄位順序。
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import time

import requests

TWSE_FMTQIK = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
TAIFEX_FUT_DAILY = "https://www.taifex.com.tw/cht/3/futDataDown"
TAIFEX_INST_BY_CONTRACT = "https://www.taifex.com.tw/cht/3/futContractsDateDown"
TAIFEX_LARGE_TRADER = "https://www.taifex.com.tw/cht/3/largeTraderFutDown"
TAIFEX_VIX = "https://www.taifex.com.tw/cht/7/getVixData"

_session = requests.Session()
_session.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def _request(method: str, url: str, retries: int = 3, **kwargs) -> requests.Response:
    for attempt in range(retries):
        try:
            resp = _session.request(method, url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def num(text) -> float | None:
    """'1,234' / '+12.5' / '-' / '' → float 或 None。"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("+", "")
    if s in ("", "-", "--", "—", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def csv_rows(text: str) -> list[dict[str, str]]:
    """把期交所 CSV 轉成以去空白表頭為 key 的 dict 列表。"""
    reader = csv.reader(io.StringIO(text.strip()))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    return [
        {header[i]: cell.strip() for i, cell in enumerate(r) if i < len(header)}
        for r in rows[1:]
    ]


def _taifex_csv(url: str, date: dt.date, **extra) -> list[dict[str, str]]:
    d = date.strftime("%Y/%m/%d")
    resp = _request("POST", url, data={"queryStartDate": d, "queryEndDate": d, **extra})
    text = resp.content.decode("cp950", errors="replace")
    # 查無資料時期交所回傳 HTML 頁面而不是 CSV
    if "<html" in text[:500].lower():
        return []
    return csv_rows(text)


def _col(row: dict[str, str], *keywords: str) -> str | None:
    """找第一個表頭同時包含所有關鍵字的欄位值。"""
    for key, value in row.items():
        if all(k in key for k in keywords):
            return value
    return None


# --------------------------------------------------------------------------- 現貨


def fetch_taiex(date: dt.date) -> dict | None:
    """加權指數收盤與漲跌點數（TWSE 每月市場成交資訊）。"""
    resp = _request(
        "GET", TWSE_FMTQIK, params={"date": date.strftime("%Y%m01"), "response": "json"}
    )
    payload = resp.json()
    if payload.get("stat") != "OK":
        return None
    fields = payload["fields"]
    i_date = 0
    i_close = next(i for i, f in enumerate(fields) if "加權" in f)
    i_chg = next(i for i, f in enumerate(fields) if "漲跌" in f)
    roc = f"{date.year - 1911}/{date:%m/%d}"
    for row in payload["data"]:
        if row[i_date].strip() == roc:
            return {"close": num(row[i_close]), "change": num(row[i_chg])}
    return None


# --------------------------------------------------------------------------- 期貨


def fetch_futures_daily(date: dt.date, commodity: str) -> dict | None:
    """單一商品（TX/MTX/TMF）一般交易時段的近月行情與全市場未平倉量。"""
    rows = _taifex_csv(TAIFEX_FUT_DAILY, date, down_type="1", commodity_id=commodity)
    rows = [
        r for r in rows
        if (_col(r, "交易時段") or "一般") == "一般"
        and "/" not in (_col(r, "到期月份") or "")  # 排除價差組合
    ]
    if not rows:
        return None
    # 依到期月份排序取近月（週契約如 202610W2 排在月契約之後即可忽略）
    monthly = sorted(
        (r for r in rows if (_col(r, "到期月份") or "").strip().isdigit()),
        key=lambda r: _col(r, "到期月份"),
    )
    front = monthly[0] if monthly else rows[0]
    oi_total = sum(num(_col(r, "未沖銷")) or 0 for r in rows)
    return {
        "close": num(_col(front, "收盤價")),
        "change": num(_col(front, "漲跌價")),
        "volume": num(_col(front, "成交量")),
        "market_oi": oi_total,
    }


IDENTITY = {"自營商": "dealer", "投信": "trust", "外資": "foreign"}


def fetch_institutional(date: dt.date, commodity_id: str) -> dict | None:
    """三大法人在單一期貨契約的交易口數淨額與未平倉淨額。

    commodity_id: TXF 臺股期貨、MXF 小型臺指、TMF 微型臺指。
    """
    rows = _taifex_csv(TAIFEX_INST_BY_CONTRACT, date, commodityId=commodity_id)
    out: dict[str, dict] = {}
    for r in rows:
        ident = _col(r, "身份別") or ""
        key = next((v for k, v in IDENTITY.items() if k in ident), None)
        if key is None:
            continue
        out[key] = {
            "trade_net": num(_col(r, "多空", "交易", "口數")),
            "oi_long": num(_col(r, "多方", "未平倉", "口數")),
            "oi_short": num(_col(r, "空方", "未平倉", "口數")),
            "oi_net": num(_col(r, "多空", "未平倉", "口數")),
        }
    return out or None


def fetch_large_traders(date: dt.date, contract: str = "TX") -> dict | None:
    """大額交易人未沖銷部位（所有月份合計），分「全部交易人」與「特定法人」。"""
    rows = _taifex_csv(TAIFEX_LARGE_TRADER, date)
    out = {}
    for r in rows:
        if (_col(r, "商品", "代號") or _col(r, "契約") or "").strip() != contract:
            continue
        if (_col(r, "到期月份") or "").strip() not in ("999999", "所有契約"):
            continue
        kind = "institution" if (_col(r, "交易人類別") or "").strip() == "1" else "all"
        b5, s5 = num(_col(r, "前五大", "買")), num(_col(r, "前五大", "賣"))
        b10, s10 = num(_col(r, "前十大", "買")), num(_col(r, "前十大", "賣"))
        out[kind] = {
            "top5_net": (b5 or 0) - (s5 or 0),
            "top10_net": (b10 or 0) - (s10 or 0),
            "market_oi": num(_col(r, "全市場")),
        }
    return out or None


def fetch_vix(date: dt.date) -> float | None:
    """臺指選擇權波動率指數當日最後一筆值（期交所每日分鐘檔）。"""
    try:
        resp = _request("GET", TAIFEX_VIX, params={"filesname": date.strftime("%Y%m%d")})
    except requests.RequestException:
        return None
    text = resp.content.decode("cp950", errors="replace")
    values = []
    for line in text.splitlines():
        parts = line.replace("\t", ",").split(",")
        if len(parts) >= 2 and (v := num(parts[-1])) is not None:
            values.append(v)
    return values[-1] if values else None
