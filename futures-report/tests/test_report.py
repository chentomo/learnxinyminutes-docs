import datetime as dt

from report import fetch, metrics
from report.mock import mock_history
from report.render import build_view, render_html


def test_csv_rows_strips_headers_and_blank_lines():
    text = "日期 , 身份別 ,多空未平倉口數淨額\n2026/09/29,外資及陸資,\"-79,029\"\n\n"
    rows = fetch.csv_rows(text)
    assert rows == [{"日期": "2026/09/29", "身份別": "外資及陸資", "多空未平倉口數淨額": "-79,029"}]
    assert fetch.num(rows[0]["多空未平倉口數淨額"]) == -79029


def test_num_handles_placeholders():
    assert fetch.num("-") is None
    assert fetch.num("") is None
    assert fetch.num("+1,234.5") == 1234.5


def test_institutional_parsing(monkeypatch):
    header = ("日期,商品名稱,身份別,多方交易口數,空方交易口數,多空交易口數淨額,"
              "多方未平倉口數,空方未平倉口數,多空未平倉口數淨額")
    body = [
        "2026/09/29,臺股期貨,自營商,5000,4019,981,9000,9488,-488",
        "2026/09/29,臺股期貨,投信,10,62,-52,73000,188,72812",
        "2026/09/29,臺股期貨,外資及陸資,40000,41009,-1009,10000,89029,-79029",
    ]
    monkeypatch.setattr(fetch, "_taifex_csv", lambda *a, **k: fetch.csv_rows("\n".join([header, *body])))
    inst = fetch.fetch_institutional(dt.date(2026, 9, 29), "TXF")
    assert inst["foreign"] == {"trade_net": -1009, "oi_long": 10000, "oi_short": 89029, "oi_net": -79029}
    assert inst["dealer"]["oi_net"] == -488


def test_retail_position_is_mirror_of_institutions():
    inst = {"foreign": {"oi_net": -4000}, "trust": {"oi_net": 0}, "dealer": {"oi_net": -1550}}
    r = metrics.retail_position(inst, 33_000)
    assert r["net"] == 5550
    assert round(r["ratio"], 3) == 0.168


def test_temperature_bounds():
    hist = mock_history(dt.date(2026, 9, 29), count=10)
    temps = [metrics.daily_temperature(r, hist[i - 1] if i else None) for i, r in enumerate(hist)]
    assert all(0 <= t <= 1 for t in temps)
    assert 0 <= metrics.weekly_temperature(temps) <= 1


def test_render_demo_and_missing_fields():
    hist = mock_history(dt.date(2026, 9, 29))
    html = render_html(build_view(hist, "測試"))
    assert "2026-09-29" in html and "echarts" in html
    # 單一來源失敗（例如大額交易人、VIX 抓不到）時仍能出報表
    hist[-1]["large"] = None
    hist[-1]["vix"] = None
    html = render_html(build_view(hist, "測試"))
    assert "—" in html


def test_send_telegram_photo(monkeypatch, tmp_path):
    from report import notify

    png = tmp_path / "r.png"
    png.write_bytes(b"\x89PNG")
    sent = {}

    class Resp:
        ok = True

    def fake_post(url, data, files, timeout):
        sent.update(url=url, data=data, name=files["photo"][0])
        return Resp()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(notify.requests, "post", fake_post)
    assert notify.telegram_configured()
    notify.send_telegram_photo(png, "日報")
    assert sent == {"url": "https://api.telegram.org/bot123:abc/sendPhoto",
                    "data": {"chat_id": "42", "caption": "日報"}, "name": "r.png"}
