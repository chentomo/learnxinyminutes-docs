"""由原始資料推算的衍生指標。

這裡的「九大交易人」與「溫度計」是暫定算法——原版日報沒有公開定義，
確認後只要改這個檔案即可，其他程式不用動。
"""
from __future__ import annotations


def retail_position(inst: dict | None, market_oi: float | None) -> dict:
    """散戶籌碼 = 全市場扣除三大法人。

    全市場多單 = 空單 = 未平倉量，所以
      散戶多單 = OI − 法人多單、散戶空單 = OI − 法人空單
      散戶淨部位 = 法人空單 − 法人多單 = −(法人淨部位)
      多空比 = 散戶淨部位 ÷ 全市場未平倉量
    """
    if not inst or not market_oi:
        return {"net": None, "ratio": None}
    inst_net = sum((v.get("oi_net") or 0) for v in inst.values())
    net = -inst_net
    return {"net": net, "ratio": net / market_oi}


def nine_traders_net(large: dict | None) -> float | None:
    """暫定：前十大「全部交易人」淨部位（五大、十大欄位顯示的是特定法人）。"""
    if not large or "all" not in large:
        return None
    return large["all"]["top10_net"]


def _sign(value: float | None, invert: bool = False) -> float:
    """多方訊號 1、空方 0、無資料或持平 0.5。"""
    if value is None or value == 0:
        return 0.5
    bullish = value > 0
    if invert:
        bullish = not bullish
    return 1.0 if bullish else 0.0


def daily_temperature(rec: dict, prev: dict | None) -> float | None:
    """暫定的當日多空溫度（0–1，越高越偏多），六個訊號等權平均：

    1. 加權指數漲跌            2. 台指期漲跌
    3. 外資台指期未平倉增減    4. 十大特定法人淨部位
    5. 小台散戶多空比（反指標） 6. VIX 漲跌（反指標）
    """
    if not rec.get("taiex"):
        return None
    foreign_oi_change = None
    if prev:
        cur = _get(rec, "inst", "TXF", "foreign", "oi_net")
        old = _get(prev, "inst", "TXF", "foreign", "oi_net")
        if cur is not None and old is not None:
            foreign_oi_change = cur - old
    vix_change = None
    if rec.get("vix") is not None and prev and prev.get("vix") is not None:
        vix_change = rec["vix"] - prev["vix"]
    signals = [
        _sign(_get(rec, "taiex", "change")),
        _sign(_get(rec, "tx", "change")),
        _sign(foreign_oi_change),
        _sign(_get(rec, "large", "institution", "top10_net")),
        _sign(retail_position(_get(rec, "inst", "MXF"), _get(rec, "mxf", "market_oi"))["ratio"], invert=True),
        _sign(vix_change, invert=True),
    ]
    return sum(signals) / len(signals)


def weekly_temperature(daily_values: list[float | None]) -> float | None:
    """當周溫度 = 最近 5 個交易日的當日溫度平均。"""
    vals = [v for v in daily_values[-5:] if v is not None]
    return sum(vals) / len(vals) if vals else None


def _get(d: dict | None, *path):
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d
