"""把各來源的資料組成一筆每日紀錄。"""
from __future__ import annotations

import datetime as dt
import logging

from . import fetch

log = logging.getLogger(__name__)


def _safe(label: str, fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # 單一來源失敗不影響其他欄位
        log.warning("%s 抓取失敗：%s", label, exc)
        return None


def collect_day(date: dt.date) -> dict | None:
    """抓取某交易日的所有資料；休市（現貨與台指期都沒資料）時回傳 None。"""
    taiex = _safe("加權指數", fetch.fetch_taiex, date)
    tx = _safe("台指期行情", fetch.fetch_futures_daily, date, "TX")
    if taiex is None and tx is None:
        return None
    return {
        "date": date.isoformat(),
        "taiex": taiex,
        "tx": tx,
        "mxf": _safe("小台行情", fetch.fetch_futures_daily, date, "MTX"),
        "tmf": _safe("微台行情", fetch.fetch_futures_daily, date, "TMF"),
        "vix": _safe("VIX", fetch.fetch_vix, date),
        "inst": {
            cid: _safe(f"三大法人 {cid}", fetch.fetch_institutional, date, cid)
            for cid in ("TXF", "MXF", "TMF")
        },
        "large": _safe("大額交易人", fetch.fetch_large_traders, date),
    }
