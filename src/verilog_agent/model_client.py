"""Model abstraction, deterministic scripted client, and optional OpenAI client."""

from __future__ import annotations

import os
import re
from collections import deque
from collections.abc import Iterable
from typing import Any, Protocol

from verilog_agent.errors import InvalidModelOutputError, ModelClientError
from verilog_agent.models import Diagnostic
from verilog_agent.prompts import generation_prompt, repair_prompt
from verilog_agent.spec import TaskSpec

MAX_MODEL_OUTPUT_CHARS = 100_000
MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", re.IGNORECASE)
ENDMODULE_RE = re.compile(r"\bendmodule\b", re.IGNORECASE)
FENCE_RE = re.compile(
    r"\A"
    + chr(96) * 3
    + r"(?:verilog|systemverilog|sv)?[ \t]*\r?\n(?P<body>.*)\r?\n"
    + chr(96) * 3
    + r"[ \t]*\Z",
    re.IGNORECASE | re.DOTALL,
)
FORBIDDEN_RE = re.compile(
    r"(?:\x60include\b|\$(?:system|display|write|strobe|monitor|finish|stop|fatal|"
    r"error|warning|info|fopen|fclose|fread|fwrite|fdisplay|fstrobe|dumpfile|"
    r"dumpvars|readmem[hb]|writemem[hb])\b|\b(?:initial|force|release)\b|"
    r"(?:\btb|\$root)\s*\.|\b(?:import|export)\s+\"DPI|\b(?:VPI|PLI)\b)",
    re.IGNORECASE,
)


class ModelClient(Protocol):
    def generate_rtl(self, spec: TaskSpec) -> str: ...

    def repair_rtl(
        self,
        spec: TaskSpec,
        current_rtl: str,
        diagnostic: Diagnostic,
        attempt: int,
        remaining_retries: int,
    ) -> str: ...


def _without_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\r\n]*", "", source)


def clean_and_validate_model_output(raw: str, module_name: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidModelOutputError("model response is empty")
    if len(raw) > MAX_MODEL_OUTPUT_CHARS:
        raise InvalidModelOutputError(
            f"model response exceeds {MAX_MODEL_OUTPUT_CHARS} character limit"
        )
    value = raw.strip()
    fence = FENCE_RE.fullmatch(value)
    if fence:
        value = fence.group("body").strip()
    if chr(96) * 3 in value:
        raise InvalidModelOutputError("model response contains an incomplete or extra code fence")
    uncommented = _without_comments(value)
    modules = MODULE_RE.findall(uncommented)
    if len(modules) != 1 or len(ENDMODULE_RE.findall(uncommented)) != 1:
        raise InvalidModelOutputError("model response must contain exactly one complete module")
    if modules[0] != module_name:
        raise InvalidModelOutputError(
            f"model returned module {modules[0]!r}; expected {module_name!r}"
        )
    forbidden = FORBIDDEN_RE.search(uncommented)
    if forbidden:
        raise InvalidModelOutputError(
            f"model response contains forbidden construct {forbidden.group(0)!r}"
        )
    return value + "\n"


class ScriptedModelClient:
    """Return preloaded responses in order; intended for deterministic tests."""

    def __init__(self, responses: Iterable[str]) -> None:
        self._responses = deque(responses)
        self.calls: list[str] = []

    def _next(self, operation: str) -> str:
        self.calls.append(operation)
        if not self._responses:
            raise ModelClientError(f"scripted client has no response left for {operation}")
        return self._responses.popleft()

    def generate_rtl(self, spec: TaskSpec) -> str:
        del spec
        return self._next("generate")

    def repair_rtl(
        self,
        spec: TaskSpec,
        current_rtl: str,
        diagnostic: Diagnostic,
        attempt: int,
        remaining_retries: int,
    ) -> str:
        del spec, current_rtl, diagnostic, attempt, remaining_retries
        return self._next("repair")


class OpenAIModelClient:
    """Optional OpenAI Responses API adapter with environment-only configuration."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL")
        self.timeout_seconds = timeout_seconds
        if not self._api_key:
            raise ModelClientError("OPENAI_API_KEY is not set")
        if not self.model:
            raise ModelClientError("OPENAI_MODEL is not set")

    @classmethod
    def from_environment(cls) -> OpenAIModelClient:
        return cls()

    def __repr__(self) -> str:
        return (
            f"OpenAIModelClient(model={self.model!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, api_key=<redacted>)"
        )

    def _request(self, prompt: str) -> str:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ModelClientError(
                "optional OpenAI dependency is not installed; install the 'llm' extra"
            ) from exc
        try:
            client = OpenAI(api_key=self._api_key, timeout=self.timeout_seconds)
            response: Any = client.responses.create(model=self.model, input=prompt)
        except Exception as exc:
            raise ModelClientError(
                f"OpenAI request failed: {type(exc).__name__}"
            ) from exc
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise ModelClientError("OpenAI response did not contain non-empty output_text")
        return output_text

    def generate_rtl(self, spec: TaskSpec) -> str:
        return self._request(generation_prompt(spec))

    def repair_rtl(
        self,
        spec: TaskSpec,
        current_rtl: str,
        diagnostic: Diagnostic,
        attempt: int,
        remaining_retries: int,
    ) -> str:
        return self._request(
            repair_prompt(
                spec, current_rtl, diagnostic, attempt, remaining_retries
            )
        )
