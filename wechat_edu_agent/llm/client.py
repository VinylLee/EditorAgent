from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import AppConfig
from utils.file_utils import ensure_dir


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        json_mode: str = "off",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.json_mode = json_mode
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.trace_path: Path | None = None
        self.last_finish_reason: str | None = None

    @classmethod
    def from_config(cls, config: AppConfig) -> "LLMClient":
        return cls(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            model=config.llm_model,
            json_mode=config.json_mode,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    def _build_response_format(self, json_schema: dict | None) -> dict | None:
        if self.json_mode == "json_object":
            return {"type": "json_object"}
        if self.json_mode == "json_schema" and json_schema:
            return {"type": "json_schema", "json_schema": json_schema}
        return None

    def set_trace_path(self, trace_path: Path | str | None) -> None:
        if trace_path is None:
            self.trace_path = None
            return
        path = Path(trace_path)
        ensure_dir(path.parent)
        self.trace_path = path

    def _append_trace(self, payload: dict[str, Any]) -> None:
        if not self.trace_path:
            return
        try:
            with self.trace_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict | None = None,
        request_tag: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if response_format:
            request["response_format"] = response_format
        trace = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tag": request_tag,
            "base_url": self.base_url,
            "model": self.model,
            "json_mode": self.json_mode,
            "temperature": request["temperature"],
            "max_tokens": request["max_tokens"],
            "response_format": response_format,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
        try:
            response = self.client.chat.completions.create(**request)
        except Exception as exc:
            trace["error"] = str(exc)
            self._append_trace(trace)
            raise
        choice = response.choices[0]
        self.last_finish_reason = choice.finish_reason
        content = choice.message.content or ""
        trace["finish_reason"] = self.last_finish_reason
        trace["response"] = content
        self._append_trace(trace)
        return content

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None = None,
        request_tag: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        response_format = self._build_response_format(json_schema)
        return self.chat_text(
            system_prompt,
            user_prompt,
            response_format=response_format,
            request_tag=request_tag,
            temperature=temperature,
            max_tokens=max_tokens,
        )
