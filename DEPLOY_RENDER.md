# 台股 AI Agent：部署到 Render 免費方案

## 先講結論

你提供的程式目前是**命令列（CLI）程式**：

```bash
python -m app 2330 --question "請分析台積電的技術面、基本面與近期新聞"
```

它沒有 HTTP Web Server，因此**不能把原始 `app.zip` 直接當成 Render Web Service 部署**；Render 會因為找不到監聽中的 HTTP port 而部署失敗。

我已準備一份可部署版本：

- 保留原本的 `python -m app ...` CLI。
- 新增 `web.py`，提供 `/healthz` 與 `POST /analyze` API。
- 加入 Flask 與 Gunicorn。
- 預設 `USE_LLM=false`，避免你不小心產生 LLM API 費用。

> Render 的免費主機適合練習、展示與個人專案，不適合正式生產服務。這個專案只做唯讀研究，不會連接券商或下單。

---

## 一、先下載／解壓可部署版本

使用我提供的 `render-deploy` 資料夾，資料夾最上層應該看到：

```text
render-deploy/
├── app/
├── tests/
├── web.py
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

**重要：** `app/` 和 `tests/` 必須位於 Git Repository 根目錄下，不要變成：

```text
render-deploy/app/app/      # 錯誤的多一層目錄
```

---

## 二、在本機先測試

請在 `render-deploy` 目錄執行：

### 1. 建立虛擬環境與安裝套件

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 執行測試

```bash
pytest
```

預期會看到 4 個測試通過。

### 3. 先用假資料跑 CLI

這一步不需要 Yahoo Finance 網路，也不會呼叫 LLM：

```bash
STOCK_DATA_PROVIDER=mock USE_LLM=false python -m app 2330 --mock --no-llm
```

Windows PowerShell：

```powershell
$env:STOCK_DATA_PROVIDER="mock"
$env:USE_LLM="false"
python -m app 2330 --mock --no-llm
```

### 4. 本機啟動 HTTP API

```bash
STOCK_DATA_PROVIDER=mock USE_LLM=false gunicorn --bind 127.0.0.1:10000 web:app
```

另一個終端測試：

```bash
curl http://127.0.0.1:10000/healthz
```

預期：

```json
{"status":"ok"}
```

測試分析 API：

```bash
curl -X POST http://127.0.0.1:10000/analyze \\
  -H "Content-Type: application/json" \\
  -d '{"symbol":"2330","question":"只看股價"}'
```

若以上成功，才進入 Render 部署。

---

## 三、放到 GitHub

Render 需要從 Git Repository 讀取程式。建議建立一個**Private Repository**。

### 方法 A：GitHub 網頁

1. 到 [GitHub New Repository](https://github.com/new)。
2. 建立一個 Private Repository，例如 `taiwan-stock-agent-render`。
3. 上傳 `render-deploy` 裡的**所有內容**，不是上傳 `render-deploy` 這一層資料夾。
4. 確認 GitHub 頁面能直接看到 `app/`、`web.py`、`requirements.txt`。

### 方法 B：命令列

在 `render-deploy` 目錄執行：

```bash
git init
git branch -M main
git add app tests web.py requirements.txt pyproject.toml .env.example .gitignore README.md
git commit -m "prepare Render deployment"
gh repo create taiwan-stock-agent-render --private --source=. --remote=origin --push
```

如果你已經有自己的 GitHub Repository，改用：

```bash
git remote add origin https://github.com/你的帳號/你的Repository.git
git push -u origin main
```

### 金鑰安全檢查

- **不要**建立或上傳 `.env`。
- 可以上傳 `.env.example`，因為它不應該包含真正的金鑰。
- `.gitignore` 已經忽略 `.env` 與 SQLite 資料庫。
- 如果曾把真正的 `OPENAI_API_KEY` 提交到 Git，請立即到提供者後台撤銷並重新產生，不要只刪除檔案。

---

## 四、在 Render 建立免費 Web Service

官方入口：[Render Dashboard](https://dashboard.render.com/)

1. 登入 Render，連接 GitHub。
2. 點 **New → Web Service**。
3. 選擇你的 `taiwan-stock-agent-render` Repository。
4. 設定：

| Render 欄位 | 填入值 |
|---|---|
| **Name** | `taiwan-stock-agent` 或你喜歡的名稱 |
| **Branch** | `main` |
| **Language / Runtime** | `Python 3`（若介面顯示 Python 即可） |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --bind 0.0.0.0:$PORT web:app` |
| **Instance Type / Plan** | `Free` |
| **Health Check Path** | `/healthz`（如果介面提供此欄位） |

`0.0.0.0` 和 `$PORT` 很重要。Render 官方要求 Web Service 在 `0.0.0.0` 監聽，並建議使用平台提供的 `PORT` 環境變數。

---

## 五、設定 Environment Variables

在 Render 的 **Environment → Environment Variables** 加入：

| Key | Value | 建議 |
|---|---|---|
| `USE_LLM` | `false` | 第一次部署先用這個，避免 API 費用 |
| `STOCK_DATA_PROVIDER` | `yfinance` | 使用 Yahoo Finance 研究資料 |
| `STOCK_AGENT_DB` | `data/agent.db` | 只適合短期暫存 |
| `NEWS_LIMIT` | `8` | 新聞最多取 8 筆 |

第一次部署**不要填** `OPENAI_API_KEY`。

這個專案即使沒有金鑰，也會使用內建的本地 Markdown 報告模板；因此可以先確認免費部署和行情資料流程都正常。

### 如果你確定要使用 LLM

再另外加入：

| Key | Value |
|---|---|
| `USE_LLM` | `true` |
| `OPENAI_API_KEY` | 在 Render 的 Secret 欄位貼入金鑰 |
| `OPENAI_API_BASE` | 如果使用相容 API 才填，否則留空 |
| `LLM_MODEL` | 你的 API 供應商實際提供的模型名稱 |

> Render 免費不代表 LLM API 免費。只要 `USE_LLM=true` 且金鑰有效，分析請求可能產生供應商費用；請自行設定供應商的用量上限。

按 **Create Web Service**，等待 Build 與 Deploy 完成。

---

## 六、部署後測試

Render 完成後會給你一個類似以下的網址：

```text
https://taiwan-stock-agent-xxxx.onrender.com
```

### 1. Health Check

```bash
curl https://taiwan-stock-agent-xxxx.onrender.com/healthz
```

預期：

```json
{"status":"ok"}
```

### 2. 分析一檔股票

```bash
curl -X POST https://taiwan-stock-agent-xxxx.onrender.com/analyze \\
  -H "Content-Type: application/json" \\
  -d '{"symbol":"2330","question":"請分析價格、技術面與近期新聞"}'
```

回應會是 JSON，主要欄位包括：

- `report`：繁體中文 Markdown 報告
- `bundle`：結構化資料、來源與資料缺口
- `analysis_id`：SQLite 中的暫存分析 ID

如果只在瀏覽器網址列開啟根網址，會看到服務狀態 JSON；分析功能目前是 API，需用 `curl`、Postman 或前端頁面呼叫 `POST /analyze`。

---

## 七、免費方案的三個限制

### 1. 閒置會休眠

Render 免費 Web Service 閒置 15 分鐘後會停止；下一次收到請求時會喚醒，通常需要約 1 分鐘。第一次測試看到等待頁是正常現象。

### 2. SQLite 不保證保存

Render 免費服務的本機檔案系統是暫時的。服務重啟、重新部署或休眠時，`data/agent.db` 可能消失。因此：

- `analysis_id` 只是短期暫存用途。
- 不要把 Render 上的 SQLite 當正式備份。
- 需要長期保存時，再改成外部資料庫；Render 的免費 PostgreSQL 也有官方列出的 30 天期限，不能當永久免費備份。

### 3. 不是正式生產環境

Render 官方把 Free instance 定位為測試、興趣專案與預覽用途；資源是 0.1 CPU / 512 MB RAM，且有每月免費 instance hours、頻寬與建置用量限制。

---

## 八、常見錯誤排除

### `No open ports detected`

確認 Start Command 完全是：

```bash
gunicorn --bind 0.0.0.0:$PORT web:app
```

不要使用原本的：

```bash
python -m app 2330
```

後者是一次性 CLI，執行完會結束，也不會監聽 HTTP port。

### `ModuleNotFoundError: No module named 'app'`

確認 Repository 根目錄直接包含 `app/`，而不是多包一層目錄；同時確認 Render 的 **Root Directory** 留空。

### `ModuleNotFoundError: No module named 'flask'`

確認 `requirements.txt` 已包含：

```text
flask>=3.0,<4
gunicorn>=23,<24
```

並按 Render 的 **Manual Deploy → Deploy latest commit** 重新部署。

### API 回傳 `analysis failed`

先檢查 Render Logs。常見原因：

- `yfinance` 暫時取不到資料或被上游限制。
- 股票代號不正確；上市通常用 `2330`，上櫃可用 `6488.TWO`。
- 把 `USE_LLM` 設成 `true`，但模型名稱或 API 設定不正確。
- 免費服務正在喚醒，稍等後再試。

若要分辨是不是行情網路問題，可在本機先用：

```bash
STOCK_DATA_PROVIDER=mock USE_LLM=false gunicorn --bind 127.0.0.1:10000 web:app
```

### 金鑰或費用疑慮

把 Render 上的 `USE_LLM` 設成 `false`，並移除不需要的 `OPENAI_API_KEY`。本專案沒有金鑰時仍可產生本地模板報告。

---

## 官方參考

- [Render：免費部署與限制](https://render.com/docs/free)
- [Render：Web Services](https://render.com/docs/web-services)
- [Render：首次部署](https://render.com/docs/your-first-deploy)

