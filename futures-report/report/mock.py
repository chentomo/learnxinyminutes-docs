"""產生格式與真實資料相同的模擬資料，用來在連不到期交所時預覽版面。"""
from __future__ import annotations

import datetime as dt
import random


def trading_days(end: dt.date, count: int) -> list[dt.date]:
    days, d = [], end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    return list(reversed(days))


def mock_history(end: dt.date, count: int = 45, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    index = 44_000.0
    foreign_oi, trust_oi, dealer_oi = -60_000.0, 70_000.0, 500.0
    mxf_inst, tmf_inst = -3_000.0, -10_000.0
    vix = 22.0
    records = []
    for day in trading_days(end, count):
        change = rng.gauss(40, 380)
        index += change
        basis = rng.uniform(-50, 200)
        tx_change = change + rng.gauss(0, 40)
        vix_new = max(12.0, vix + rng.gauss(0, 1.2) - change / 500)
        f_new = foreign_oi + rng.gauss(0, 2_500)
        t_new = trust_oi + rng.gauss(30, 300)
        d_new = dealer_oi + rng.gauss(0, 900)
        mxf_inst = 0.85 * mxf_inst + rng.gauss(0, 1_800) - change * 2
        tmf_inst = 0.85 * tmf_inst + rng.gauss(0, 4_000) - change * 5
        mxf_oi = rng.uniform(30_000, 45_000)
        tmf_oi = rng.uniform(60_000, 90_000)

        def split(total, share=(0.7, 0.1, 0.2)):
            return {
                k: {"trade_net": round(rng.gauss(0, 800)), "oi_net": round(total * s)}
                for k, s in zip(("foreign", "trust", "dealer"), share)
            }

        records.append({
            "date": day.isoformat(),
            "taiex": {"close": round(index, 2), "change": round(change, 2)},
            "tx": {"close": round(index + basis), "change": round(tx_change),
                   "volume": round(rng.uniform(80_000, 140_000)), "market_oi": 90_000},
            "mxf": {"market_oi": round(mxf_oi)},
            "tmf": {"market_oi": round(tmf_oi)},
            "vix": round(vix_new, 2),
            "inst": {
                "TXF": {
                    "foreign": {"trade_net": round(f_new - foreign_oi + rng.gauss(0, 300)), "oi_net": round(f_new)},
                    "trust": {"trade_net": round(t_new - trust_oi), "oi_net": round(t_new)},
                    "dealer": {"trade_net": round(d_new - dealer_oi + rng.gauss(0, 200)), "oi_net": round(d_new)},
                },
                "MXF": split(mxf_inst),
                "TMF": split(tmf_inst),
            },
            "large": {
                "all": {"top5_net": round(rng.gauss(0, 3_000)), "top10_net": round(rng.gauss(0, 4_000))},
                "institution": {"top5_net": round(rng.gauss(0, 2_500)), "top10_net": round(rng.gauss(-1_000, 3_500))},
            },
        })
        foreign_oi, trust_oi, dealer_oi, vix = f_new, t_new, d_new, vix_new
    return records
