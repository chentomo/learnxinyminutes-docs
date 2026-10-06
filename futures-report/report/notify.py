"""把日報圖片傳到 Telegram。

需要兩個環境變數（在 GitHub 上設定成 Secrets）：
  TELEGRAM_BOT_TOKEN  向 @BotFather 建立機器人時拿到的 token
  TELEGRAM_CHAT_ID    要收圖的聊天室 ID（個人、群組或頻道）
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send_telegram_photo(png_path: Path, caption: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    with open(png_path, "rb") as f:
        resp = requests.post(
            API.format(token=token, method="sendPhoto"),
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": (png_path.name, f, "image/png")},
            timeout=60,
        )
    if not resp.ok:
        raise RuntimeError(f"Telegram 傳送失敗：{resp.status_code} {resp.text[:300]}")
