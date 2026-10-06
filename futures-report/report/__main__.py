"""命令列入口。

  python -m report demo                       用模擬資料產生報表（不需網路）
  python -m report daily [--date YYYY-MM-DD]  抓當日資料、存檔並產生報表
  python -m report backfill --start D --end D 回補歷史資料（趨勢圖需要約 40 個交易日）
  python -m report render [--date YYYY-MM-DD] 只用資料庫裡的資料重新產生報表

加上 --png 會同時輸出截圖。
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
from pathlib import Path

from .render import CHART_DAYS, build_view, render_html
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("report")


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def write_report(store: Store, date: str, args) -> None:
    history = store.history(date, CHART_DAYS + 5)
    if not history or history[-1]["date"] != date:
        sys.exit(f"資料庫裡沒有 {date} 的資料")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"report-{date}.html"
    html_path.write_text(render_html(build_view(history, args.title)), encoding="utf-8")
    print(f"HTML：{html_path}")
    if args.png:
        from .snapshot import html_to_png

        png_path = html_path.with_suffix(".png")
        html_to_png(html_path, png_path)
        print(f"PNG ：{png_path}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="report", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "report.db"))
    parser.add_argument("--out", default=str(ROOT / "output"))
    parser.add_argument("--title", default="台指期籌碼日報")
    parser.add_argument("--png", action="store_true", help="同時輸出 PNG 截圖")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("demo")
    p.add_argument("--date", type=_date, default=dt.date.today())
    p = sub.add_parser("daily")
    p.add_argument("--date", type=_date, default=dt.date.today())
    p = sub.add_parser("backfill")
    p.add_argument("--start", type=_date, required=True)
    p.add_argument("--end", type=_date, default=dt.date.today())
    p = sub.add_parser("render")
    p.add_argument("--date", type=_date)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "demo":
        from .mock import mock_history

        store = Store(Path(args.db).with_name("demo.db"))
        records = mock_history(args.date)
        for r in records:
            store.save(r)
        write_report(store, records[-1]["date"], args)
        return

    store = Store(args.db)
    if args.cmd == "daily":
        from .collect import collect_day

        rec = collect_day(args.date)
        if rec is None:
            sys.exit(f"{args.date} 查無資料（休市或尚未公布）")
        store.save(rec)
        write_report(store, rec["date"], args)
    elif args.cmd == "backfill":
        from .collect import collect_day

        day = args.start
        while day <= args.end:
            if day.weekday() < 5 and store.get(day.isoformat()) is None:
                rec = collect_day(day)
                log.info("%s %s", day, "OK" if rec else "休市／無資料")
                if rec:
                    store.save(rec)
                time.sleep(1.5)  # 別對期交所太密集
            day += dt.timedelta(days=1)
    elif args.cmd == "render":
        date = args.date.isoformat() if args.date else store.latest_date()
        if not date:
            sys.exit("資料庫是空的，請先執行 daily 或 backfill")
        write_report(store, date, args)


if __name__ == "__main__":
    main()
