"""LLM synthesis with a deterministic local fallback."""

from __future__ import annotations

import os

from .models import AnalysisBundle, compact_json
from .report import fallback_report


class LLMAnalyzer:
    """Turn structured evidence into a cautious Traditional Chinese report."""

    def __init__(
        self,
        model: str = "gpt-5-mini",
        enabled: bool = True,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.model = model
        self.enabled = enabled
        # None preserves the CLI's environment-variable behavior. An explicit
        # empty string intentionally disables environment fallback for web use.
        self.api_key = api_key
        self.api_base = api_base
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.enabled:
            return None
        api_key = self.api_key if self.api_key is not None else os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI

            client_kwargs = {"api_key": api_key}
            api_base = self.api_base
            if api_base is None:
                api_base = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
            if api_base:
                client_kwargs["base_url"] = api_base
            self._client = OpenAI(**client_kwargs)
            return self._client
        except Exception:
            return None

    def generate(self, bundle: AnalysisBundle) -> str:
        client = self._get_client()
        if client is None:
            return fallback_report(bundle)

        system_prompt = """
你是嚴謹的台股研究助理。請只使用使用者提供的結構化資料，不得補造價格、財務數字、新聞內容或因果關係。
用繁體中文輸出 Markdown 報告，明確區分：資料事實、技術指標、推論、風險與資料缺口。
不要提供下單、買賣、交易執行或報酬保證；結尾必須包含完整的「## Important Notice」段落。
如果資料不足，請寫「資料不足」並說明影響，不要把缺失值當成 0。
""".strip()
        user_prompt = f"使用者問題：{bundle.question}\n\n研究資料：\n{compact_json(bundle.to_dict())}"
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=2500,
                extra_body={"reasoning": {"effort": "minimal"}},
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception:
            pass
        return fallback_report(bundle)
