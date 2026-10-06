"""把每日紀錄與歷史整理成版面需要的資料，再套 Jinja2 範本輸出單一 HTML 檔。"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import metrics
from .metrics import _get

HERE = Path(__file__).parent
CHART_DAYS = 40


def _pct(a, b):
    return a / (b - a) if a is not None and b else None


def build_view(history: list[dict], title: str) -> dict:
    """history：由舊到新，最後一筆就是報表當日。"""
    rec = history[-1]
    prev = history[-2] if len(history) > 1 else None

    def kpi(block):
        close, chg = _get(rec, block, "close"), _get(rec, block, "change")
        return {"value": close, "change": chg, "pct": _pct(chg, close)}

    vix, vix_prev = rec.get("vix"), (prev or {}).get("vix")
    vix_chg = vix - vix_prev if vix is not None and vix_prev is not None else None

    inst_rows = []
    for key, label in (("foreign", "外資"), ("trust", "投信"), ("dealer", "自營")):
        cur = _get(rec, "inst", "TXF", key) or {}
        old = _get(prev, "inst", "TXF", key) or {}
        delta = None
        if cur.get("oi_net") is not None and old.get("oi_net") is not None:
            delta = cur["oi_net"] - old["oi_net"]
        inst_rows.append({"label": label, "trade": cur.get("trade_net"), "oi": cur.get("oi_net"), "delta": delta})

    big = [
        {"label": "五大", "value": _get(rec, "large", "institution", "top5_net")},
        {"label": "十大", "value": _get(rec, "large", "institution", "top10_net")},
        {"label": "九大", "value": metrics.nine_traders_net(rec.get("large"))},
    ]

    def retail(r, contract, block):
        return metrics.retail_position(_get(r, "inst", contract), _get(r, block, "market_oi"))

    retail_rows = []
    for contract, block, label in (("MXF", "mxf", "小台 MXF"), ("TMF", "tmf", "微台 TMF")):
        cur, old = retail(rec, contract, block), retail(prev, contract, block) if prev else None
        delta = cur["net"] - old["net"] if old and cur["net"] is not None and old["net"] is not None else None
        retail_rows.append({"label": label, **cur, "delta": delta})

    temps = [
        metrics.daily_temperature(r, history[i - 1] if i else None) for i, r in enumerate(history)
    ]

    window = history[-CHART_DAYS:]
    chart = {
        "dates": [r["date"] for r in window],
        "index": [_get(r, "taiex", "close") for r in window],
        "nine": [metrics.nine_traders_net(r.get("large")) for r in window],
        "foreign": [_get(r, "inst", "TXF", "foreign", "oi_net") for r in window],
        "mxf": [_ratio_pct(retail(r, "MXF", "mxf")) for r in window],
        "tmf": [_ratio_pct(retail(r, "TMF", "tmf")) for r in window],
    }

    return {
        "title": title,
        "date": rec["date"],
        "taiex": kpi("taiex"),
        "tx": kpi("tx"),
        "vix": {"value": vix, "change": vix_chg, "pct": vix_chg / vix_prev if vix_chg is not None and vix_prev else None},
        "temp_day": temps[-1],
        "temp_week": metrics.weekly_temperature(temps),
        "inst_rows": inst_rows,
        "big": big,
        "retail_rows": retail_rows,
        "nine_today": big[2]["value"],
        "foreign_today": inst_rows[0]["oi"],
        "chart": chart,
    }


def _ratio_pct(r):
    return round(r["ratio"] * 100, 1) if r["ratio"] is not None else None


def fmt_int(v):
    return "—" if v is None else f"{v:,.0f}"


def fmt_num(v, digits=2):
    return "—" if v is None else f"{v:,.{digits}f}"


def fmt_signed(v, digits=2):
    return "—" if v is None else f"{v:+,.{digits}f}"


def fmt_pct(v, digits=1):
    return "—" if v is None else f"{v * 100:.{digits}f}%"


def tone(v):
    """台股慣例：漲／多為紅、跌／空為綠。"""
    if v is None or v == 0:
        return "flat"
    return "up" if v > 0 else "down"


def render_html(view: dict) -> str:
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True)
    env.filters.update(int=fmt_int, num=fmt_num, signed=fmt_signed, pct=fmt_pct, tone=tone)
    template = env.get_template("report.html.j2")
    echarts = (HERE / "static" / "echarts.min.js").read_text(encoding="utf-8")
    return template.render(v=view, chart_json=json.dumps(view["chart"]), echarts_js=echarts)
