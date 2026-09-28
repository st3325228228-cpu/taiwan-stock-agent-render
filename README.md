# 台股 AI Agent（Python）

這是一個可在本機執行的**唯讀台股研究 Agent**，把使用者問題先交給可檢查的工具路由，再把結構化資料交給 LLM 綜合成繁體中文 Markdown 報告。

## 架構

```text
使用者問題
    ↓
ToolPlanner（判斷需要哪些資料）
    ↓
├─ 股價 Tool          → Yahoo Finance / yfinance
├─ 技術分析 Tool      → 本地計算 SMA、EMA、RSI、MACD、布林通道
├─ 基本面 Tool        → 公司摘要與估值欄位
├─ 新聞搜尋 Tool      → 近期新聞清單
└─ 資料庫 Tool        → SQLite 保存快照與歷史分析
    ↓
LLMAnalyzer（可關閉；預設 gpt-5-mini）
    ↓
Markdown 研究報告
```

## 已實作功能

- 支援上市與上櫃代號：`2330` 會正規化為 `2330.TW`；`6488.TWO` 可直接使用。
- 以問題關鍵字路由工具：價格為必選；一般分析會自動加入技術面、基本面與新聞；只問股價時會跳過其他工具。
- 技術指標採透明公式：SMA(20/60/120)、EMA(12/26)、Wilder RSI(14)、MACD(12,26,9)、布林通道(20,2)。
- 每個工具回傳 `status / data / source / retrieved_at / data_as_of`，資料不足不補 0。
- SQLite 保存分析歷史與行情快照，方便後續加入比較或回顧功能。
- LLM 可選：有 `OPENAI_API_KEY` 時使用 OpenAI-compatible Chat Completions；沒有金鑰時自動使用本地模板，不會讓整個流程失效。
- 報告會列出資料缺口、來源、風險與 `Important Notice`。
- 僅做研究與分析；不連接券商、不讀取帳戶、不下單、不改單、不撤單。

## 安裝

```bash
cd /home/ubuntu/taiwan-stock-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在本環境中 `OPENAI_API_KEY` 與 `OPENAI_API_BASE` 可由執行環境注入；在其他電腦請自行設定，不要把金鑰寫入程式碼或 Git。

## 執行

### 使用即時資料來源

```bash
python -m app 2330 \
  --question "請分析台積電的技術面、基本面與近期新聞"
```

### 不呼叫 LLM，只用本地報告模板

```bash
python -m app 2330 --no-llm
```

### 使用假資料驗證整條流程

```bash
python -m app 2330 --mock --no-llm
```

### 輸出 JSON

```bash
python -m app 2330 --mock --no-llm --json > result.json
```

## 環境變數

| 變數 | 預設 | 說明 |
|---|---:|---|
| `OPENAI_API_KEY` | 空 | LLM API 金鑰；留空會使用本地模板 |
| `OPENAI_API_BASE` | 空 | OpenAI-compatible API Base URL |
| `LLM_MODEL` | `gpt-5-mini` | 綜合分析模型；可改成環境可用的模型 |
| `USE_LLM` | `true` | `false` 時完全停用 LLM |
| `STOCK_AGENT_DB` | `data/agent.db` | SQLite 路徑 |
| `NEWS_LIMIT` | `8` | 最多保留的新聞數 |

## 測試

```bash
pytest
```

## 資料與限制

- yfinance 是研究級的 Yahoo Finance 介面，資料可能延遲、缺漏或受供應商欄位定義影響；估值關鍵數字請回到公司公告、財報與交易所資料核對。
- 日線技術分析使用完成的歷史 K 線；不把缺失值補成 0，也不把技術指標當成保證。
- 新聞標題僅是事件線索，不能代替閱讀原文、公司公告或法說資料。
- 這個專案不提供交易執行能力；若未來擴充監控或排程，也只能產生研究報告或通知，不能產生交易副作用。
