"""SQLite persistence for raw evidence snapshots and generated reports."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any

from .models import AnalysisBundle, now_utc_iso


class AnalysisStore:
    """Small SQLite store that keeps read-only research artifacts locally."""

    def __init__(self, path: str = "data/agent.db") -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path.as_posix(), check_same_thread=False)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    question TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    report TEXT NOT NULL,
                    bundle_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_analyses_symbol_created
                    ON analyses(symbol, created_at DESC);
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_created
                    ON snapshots(symbol, created_at DESC);
                """
            )

    def save_snapshot(self, symbol: str, tool: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO snapshots(symbol, created_at, tool, payload_json) VALUES (?, ?, ?, ?)",
                (symbol, now_utc_iso(), tool, json.dumps(payload, ensure_ascii=False)),
            )

    def save_analysis(self, bundle: AnalysisBundle, report: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analyses(symbol, question, created_at, report, bundle_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bundle.symbol,
                    bundle.question,
                    bundle.generated_at,
                    report,
                    json.dumps(bundle.to_dict(), ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def recent_analyses(self, symbol: str, limit: int = 3) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, symbol, question, created_at, report
                FROM analyses
                WHERE symbol = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        return [
            {
                "id": row[0],
                "symbol": row[1],
                "question": row[2],
                "created_at": row[3],
                "report": row[4],
            }
            for row in rows
        ]
