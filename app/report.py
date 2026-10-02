"""Deterministic Markdown report renderer."""

from __future__ import annotations

from typing import Any

from .models import AnalysisBundle


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "資料不足"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def _pct(value: Any) -> str:
    return "資料不足" if value is None else f"{float(value):+.2f}%"


def fallback_report(bundle: AnalysisBundle) -> str:
    """Produce a transparent report without making unsupported claims."""
    price = bundle.sections.get("price", {})
    technical = bundle.sections.get("technical", {})
    fundamentals = bundle.sections.get("fundamentals", {})
    news = bundle.sections.get("news", {})
    database = bundle.sections.get("database", {})
    price_data = price.get("data", {})
    tech_data = technical.get("data", {})
    indicators = tech_data.get("indicators", {})
    fund_data = fundamentals.get("data", {})
    news_items = news.get("data", {}).get("items", [])

    trend = indicators.get("trend", "資料不足")
    rsi = indicators.get("rsi14")
    macd_hist = indicators.get("macd_histogram")
    if trend == "偏多":
        technical_view = "收盤價位於短中期均線之上，技術面偏多，但仍需配合成交量與事件風險。"
    elif trend == "偏空":
        technical_view = "收盤價位於短中期均線之下，技術面偏空，需留意趨勢延續或反轉訊號。"
    else:
        technical_view = "均線排列未形成明確方向，技術面較接近震盪或資料不足。"

    lines = [
        f"# 台股 AI Agent 研究報告：{bundle.symbol}",
        "",
        f"> 問題：{bundle.question}",
        f"> 產生時間（UTC）：{bundle.generated_at}",
        "> 本報告為研究與教育用途，不是投資建議，也不會執行任何交易。",
        "",
        "## 結論摘要",
        f"- 最新收盤／價格：**{_fmt(price_data.get('price') or price_data.get('close'))}** {price_data.get('currency', 'TWD')}，日變動 {_pct(price_data.get('change_pct'))}。",
        f"- 技術狀態：**{trend}**；RSI(14) {_fmt(rsi)}；MACD 柱狀體 {_fmt(macd_hist)}。",
        f"- 基本面資料：{'已取得，可供交叉檢視。' if fund_data else '未取得，勿據此做估值結論。'}",
        f"- 近期新聞：取得 **{len(news_items)}** 則；新聞僅作事件線索，仍需閱讀原文與官方揭露。",
        "",
        "## 股價 Tool",
        f"- 代號：{price_data.get('symbol', bundle.symbol)}",
        f"- 開／高／低／收：{_fmt(price_data.get('open'))} / {_fmt(price_data.get('high'))} / {_fmt(price_data.get('low'))} / {_fmt(price_data.get('close'))}",
        f"- 成交量：{_fmt(price_data.get('volume'), 0)}",
        f"- 資料時間：{price_data.get('price_timestamp', price.get('data_as_of', '資料不足'))}",
        "",
        "## 技術分析 Tool",
        f"- 初步解讀：{technical_view}",
        f"- SMA20 / SMA60 / SMA120：{_fmt(indicators.get('sma20'))} / {_fmt(indicators.get('sma60'))} / {_fmt(indicators.get('sma120'))}",
        f"- EMA12 / EMA26：{_fmt(indicators.get('ema12'))} / {_fmt(indicators.get('ema26'))}",
        f"- 1 日／20 日變動：{_pct(indicators.get('change_1d_pct'))} / {_pct(indicators.get('change_20d_pct'))}",
        f"- RSI(14)：{_fmt(rsi)}；布林通道：{_fmt(indicators.get('bollinger_lower20'))} ~ { _fmt(indicators.get('bollinger_upper20')) }",
        "- 方法：日線、SMA/EMA、Wilder RSI(14)、MACD(12,26,9)、布林通道(20,2)。",
        "",
        "## 基本面 Tool",
    ]
    fundamental_keys = {
        "marketCap",
        "trailingPE",
        "priceToBook",
        "returnOnEquity",
        "revenue",
        "netIncome",
        "totalCash",
        "totalDebt",
        "freeCashflow",
    }
    if any(fund_data.get(key) is not None for key in fundamental_keys):
        for label, key in [
            ("公司名稱", "longName"),
            ("產業／類別", "industry"),
            ("市值", "marketCap"),
            ("本益比（供應商欄位）", "trailingPE"),
            ("股價淨值比（供應商欄位）", "priceToBook"),
            ("股東權益報酬率（供應商欄位）", "returnOnEquity"),
            ("資產報酬率（計算／供應商欄位）", "returnOnAssets"),
            ("營收", "revenue"),
            ("營收成長率（計算／供應商欄位）", "revenueGrowth"),
            ("營業利益率（計算／供應商欄位）", "operatingMargins"),
            ("淨利率（計算／供應商欄位）", "profitMargins"),
            ("淨利", "netIncome"),
            ("現金及約當現金", "totalCash"),
            ("總負債", "totalDebt"),
            ("自由現金流", "freeCashflow"),
        ]:
            value = fund_data.get(key)
            if key in {
                "returnOnEquity",
                "returnOnAssets",
                "revenueGrowth",
                "operatingMargins",
                "profitMargins",
            } and value is not None:
                value = f"{float(value) * 100:.2f}%"
            digits = 0 if key in {"marketCap", "revenue", "netIncome", "totalCash", "totalDebt", "freeCashflow"} else 2
            lines.append(f"- {label}：{_fmt(value, digits)}")
        if fund_data.get("financials_as_of"):
            lines.append(f"- 財報資料年度：{fund_data['financials_as_of']}")
        lines.append(f"- 資料來源：{fund_data.get('data_sources', 'Yahoo Finance')}")
        lines.append("- 備註：估值關鍵數字仍應再核對公司公告與正式財報。")
    else:
        lines.append("- 資料不足：本次沒有取得可用的基本面欄位。")
        if fund_data.get("retrieval_notes"):
            lines.append(f"- 取得備註：{fund_data['retrieval_notes']}")

    lines.extend(["", "## 新聞搜尋 Tool"])
    if news_items:
        for item in news_items[:8]:
            title = item.get("title") or "無標題"
            publisher = item.get("publisher") or "未知來源"
            published_at = item.get("published_at") or "時間未知"
            link = item.get("link") or ""
            suffix = f" — {link}" if link else ""
            lines.append(f"- {title}（{publisher}，{published_at}）{suffix}")
    else:
        lines.append("- 本次未取得新聞，或資料來源暫時沒有可用項目。")

    lines.extend(["", "## 資料庫 Tool"])
    recent = database.get("data", {}).get("recent_analyses", [])
    lines.append(f"- 已保存本次研究；同一代號的歷史分析筆數：{len(recent)}。")
    if bundle.data_gaps:
        lines.extend(["", "## 資料缺口"])
        lines.extend(f"- {gap}" for gap in bundle.data_gaps)

    lines.extend(
        [
            "",
            "## 風險與限制",
            "- 股價、基本面與新聞為研究級資料，可能延遲、缺漏或受供應商欄位定義影響；不要視為可執行報價。",
            "- 技術指標是歷史價格的數學整理，不保證未來方向；新聞標題不是完整事件分析。",
            "- 本工具不連接券商、不讀取帳戶、不產生或提交委託，且不應被改造成自動交易程式。",
            "",
            "## Important Notice",
            "> 本內容僅供資訊、研究與教育用途，不構成投資、財務、稅務或法律建議。資料可能延遲、不完整或含有供應商錯誤；使用者應自行核對交易所、公司正式公告、財報與其他可靠來源。任何投資決策與損益由使用者自行承擔。本 Agent 只產生分析與草稿，不會連接券商或執行任何買賣、下單、改單、撤單、轉帳或其他金融交易。",
        ]
    )
    return "\n".join(lines)
