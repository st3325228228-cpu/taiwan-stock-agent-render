"""Small HTTP wrapper around the original read-only Taiwan stock agent."""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from app.agent import StockAgent
from app.config import Settings
from app.database import AnalysisStore
from app.llm import LLMAnalyzer
from app.models import AnalysisRequest
from app.providers import MockDataProvider, YFinanceProvider

app = Flask(__name__)


def build_agent(api_key: str = "") -> StockAgent:
    settings = Settings.from_env()
    provider = MockDataProvider() if settings.provider == "mock" else YFinanceProvider()
    request_key = api_key.strip()
    return StockAgent(
        provider=provider,
        store=AnalysisStore(settings.database_path),
        # A request key enables LLM use even when Render keeps USE_LLM=false.
        # Passing an explicit empty string prevents accidental env-key fallback.
        llm=LLMAnalyzer(
            model=settings.llm_model,
            enabled=settings.use_llm or bool(request_key),
            api_key=request_key,
        ),
        news_limit=settings.news_limit,
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.post("/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    symbol = str(payload.get("symbol", "")).strip()
    if not symbol:
        return jsonify({"error": "symbol is required, for example 2330"}), 400

    question = str(
        payload.get(
            "question",
            "請綜合分析這檔股票的價格、技術面、基本面與近期新聞。",
        )
    ).strip()
    if not question:
        return jsonify({"error": "question must not be empty"}), 400

    request_key = payload.get("openai_api_key", "")
    if request_key is None:
        request_key = ""
    if not isinstance(request_key, str):
        return jsonify({"error": "openai_api_key must be a string"}), 400

    try:
        result = build_agent(api_key=request_key).analyze(
            AnalysisRequest(symbol=symbol, question=question)
        )
        return jsonify(result.to_dict())
    except Exception:
        app.logger.exception("stock analysis failed")
        return jsonify({"error": "analysis failed; check the service logs"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
