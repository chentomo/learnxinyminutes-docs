"""每日原始資料存在 SQLite（一天一筆 JSON），趨勢圖從這裡讀歷史。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS daily (date TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )

    def save(self, record: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO daily (date, data) VALUES (?, ?)",
            (record["date"], json.dumps(record, ensure_ascii=False)),
        )
        self.conn.commit()

    def get(self, date: str) -> dict | None:
        row = self.conn.execute("SELECT data FROM daily WHERE date = ?", (date,)).fetchone()
        return json.loads(row[0]) if row else None

    def history(self, until: str, limit: int) -> list[dict]:
        """截至 until（含）最近 limit 個交易日，日期由舊到新。"""
        rows = self.conn.execute(
            "SELECT data FROM daily WHERE date <= ? ORDER BY date DESC LIMIT ?",
            (until, limit),
        ).fetchall()
        return [json.loads(r[0]) for r in reversed(rows)]

    def latest_date(self) -> str | None:
        row = self.conn.execute("SELECT MAX(date) FROM daily").fetchone()
        return row[0]
