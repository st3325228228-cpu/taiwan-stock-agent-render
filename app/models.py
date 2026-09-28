"""Shared data contracts for the Taiwan stock research agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any
import json
import math


def now_utc_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    """Convert common scientific Python values into JSON-safe primitives."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


@dataclass
class AnalysisRequest:
    """A normalized user question for one analysis run."""

    symbol: str
    question: str
    lookback_days: int = 365
    include_news: bool = True
    include_fundamentals: bool = True


@dataclass
class ToolResult:
    """Result contract shared by every data tool."""

    tool: str
    status: str = "ok"
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    retrieved_at: str = field(default_factory=now_utc_iso)
    data_as_of: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


@dataclass
class AnalysisBundle:
    """Structured evidence passed to the report generator or LLM."""

    symbol: str
    question: str
    generated_at: str = field(default_factory=now_utc_iso)
    plan: dict[str, Any] = field(default_factory=dict)
    sections: dict[str, Any] = field(default_factory=dict)
    source_manifest: list[dict[str, Any]] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


@dataclass
class AgentResponse:
    """Final response returned by the agent."""

    report: str
    bundle: AnalysisBundle
    analysis_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.report,
            "bundle": self.bundle.to_dict(),
            "analysis_id": self.analysis_id,
        }


def compact_json(value: Any, limit: int = 20_000) -> str:
    """Serialize evidence for prompts without allowing unbounded prompt growth."""
    text = json.dumps(json_safe(value), ensure_ascii=False, indent=2)
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"
