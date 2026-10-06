# 台指期盤後籌碼日報

每個交易日收盤後，從證交所（TWSE）和期交所（TAIFEX）抓取公開資料，產生一張深色主題的籌碼日報（HTML，可另存 PNG）。

![範例（模擬資料）](docs/demo.png)

## 快速開始

```bash
cd futures-report
pip install -r requirements.txt
playwright install chromium        # 只有要輸出 PNG 才需要

# 1. 先用模擬資料看版面（不需網路）
python -m report --png demo --date 2026-09-29

# 2. 回補歷史資料（趨勢圖需要約 40 個交易日）
python -m report backfill --start 2026-08-01

# 3. 每天收盤後執行（期交所資料約 15:00–16:30 公布，建議 16:45 之後）
python -m report --png daily
```

輸出在 `output/report-YYYY-MM-DD.html` 與 `.png`；原始資料存在 `data/report.db`（SQLite）。
HTML 是單一檔案（圖表程式庫已內嵌），直接用瀏覽器打開即可，不需網路。

其他參數：`--title` 改標題、`--db` / `--out` 改路徑；
若已有 Chromium，可用環境變數 `CHROMIUM_PATH=/path/to/chrome` 取代 `playwright install`。

## 資料來源與欄位

| 區塊 | 來源 | 程式 |
|---|---|---|
| 加權指數 | TWSE 每月市場成交資訊 `FMTQIK` | `fetch_taiex` |
| 台指期／小台／微台行情、全市場未平倉 | TAIFEX 期貨每日交易行情 `futDataDown`（TX / MTX / TMF） | `fetch_futures_daily` |
| VIX | TAIFEX 臺指選擇權波動率指數每日檔 | `fetch_vix` |
| 期貨籌碼（外資／投信／自營） | TAIFEX 三大法人－區分各期貨契約 `futContractsDateDown`（TXF / MXF / TMF） | `fetch_institutional` |
| 五大／十大 | TAIFEX 大額交易人未沖銷部位 `largeTraderFutDown`（TX 所有月份、特定法人） | `fetch_large_traders` |

## 推算指標（`report/metrics.py`）

- **散戶淨未平倉** = −（三大法人淨未平倉合計）
- **散戶多空比** = 散戶淨未平倉 ÷ 全市場未平倉量
- **九大交易人（暫定）**：前十大「全部交易人」淨部位。原版定義未公開，確認後改 `nine_traders_net`。
- **當日溫度計（暫定）**：六個多空訊號等權平均——加權指數漲跌、台指期漲跌、外資未平倉增減、十大特定法人淨部位、小台散戶多空比（反指標）、VIX 漲跌（反指標）。
- **當周溫度計**：最近 5 個交易日的當日溫度平均。

顏色採台股慣例：紅＝漲／多、綠＝跌／空。

## 每天自動傳到 Telegram（GitHub Actions）

`.github/workflows/futures-report.yml` 會在週一到週五台灣時間 17:10 自動執行 `python -m report auto`：

1. 補齊最近 75 天還沒抓的資料（第一次執行會自動回補歷史，約需 10–20 分鐘）
2. 如果今天有新資料，就產生 PNG 並用 Telegram 機器人傳出
3. 把累積的資料庫 `data/report.db` 存回專案，隔天接著用

設定步驟：

1. **建立 Telegram 機器人**：在 Telegram 搜尋 `@BotFather` → 傳 `/newbot` → 依指示取名，最後會拿到一串 token（像 `123456:ABC-xyz...`）。
2. **取得聊天室 ID**：先對你的機器人傳一句任意訊息，再用瀏覽器打開
   `https://api.telegram.org/bot<你的token>/getUpdates`，找到 `"chat":{"id":` 後面那串數字。
3. **把兩個值存進 GitHub**：專案頁面 → Settings → Secrets and variables → Actions → New repository secret，
   分別新增 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
4. **啟用 Actions**：專案頁面 → Actions 分頁 → 按下啟用按鈕（fork 出來的專案預設關閉）。
5. **手動測試一次**：Actions → 台指期籌碼日報 → Run workflow。

排程只會在預設分支（master）上執行，所以這些檔案要先合併進 master。

## 尚待確認

1. 期交所下載端點的參數與 CSV 欄位是依公開格式撰寫，開發環境連不到期交所，**尚未用真實資料驗證**；第一次執行時請留意 log 裡的「抓取失敗」訊息。
2. VIX 每日檔的網址與格式最不確定，抓不到時報表會顯示「—」，不影響其他區塊。
3. 九大交易人與溫度計的算法是暫定版本。

## 測試

```bash
python -m pytest -q
```
