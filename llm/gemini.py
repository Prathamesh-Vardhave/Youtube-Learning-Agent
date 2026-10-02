from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from config.settings import settings


class GeminiConfigError(RuntimeError):
    """Raised when Gemini cannot be used because configuration is missing/invalid."""


@dataclass
class ToolCallRequest:
    """A single function/tool call the model asked for."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeminiTurnResult:
    """Result of one turn of conversation with the model."""

    text: str | None
    tool_calls: list[ToolCallRequest]
    raw: Any = None


_genai_module = None


def _genai():
    """Lazily import + configure the google-generativeai SDK exactly once."""
    global _genai_module
    if _genai_module is not None:
        return _genai_module

    if not settings.gemini_api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your Gemini API key."
        )

    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    _genai_module = genai
    return genai


def get_text_model(system_instruction: str | None = None):
    """A plain Gemini model instance for text / JSON generation (no tools)."""
    genai = _genai()
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_instruction,
    )


def get_tool_model(tools: list[Callable], system_instruction: str | None = None):
    """A Gemini model instance configured with Python-function tools for agentic tool calling."""
    genai = _genai()
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        tools=tools,
        system_instruction=system_instruction,
    )


def generate_text(prompt: str, system_instruction: str | None = None, temperature: float | None = None) -> str:
    """Single-shot plain text generation."""
    genai = _genai()
    model = get_text_model(system_instruction=system_instruction)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature if temperature is not None else settings.gemini_temperature,
        ),
    )
    return (response.text or "").strip()


def generate_json(
    prompt: str,
    schema: dict | None = None,
    system_instruction: str | None = None,
    temperature: float | None = None,
) -> str:
    """
    Single-shot generation constrained to JSON output. Returns the raw JSON
    text (callers parse it, e.g. via utils.helpers.safe_json_loads).
    """
    genai = _genai()
    model = get_text_model(system_instruction=system_instruction)
    gen_config_kwargs: dict[str, Any] = {
        "temperature": temperature if temperature is not None else settings.gemini_temperature,
        "response_mime_type": "application/json",
    }
    if schema is not None:
        gen_config_kwargs["response_schema"] = schema

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(**gen_config_kwargs),
    )
    return (response.text or "").strip()


def extract_tool_calls(response) -> list[ToolCallRequest]:
    """Pull any function-call requests out of a raw Gemini response object."""
    calls: list[ToolCallRequest] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            fn = getattr(part, "function_call", None)
            if fn and getattr(fn, "name", None):
                calls.append(ToolCallRequest(name=fn.name, args=dict(fn.args or {})))
    return calls


def extract_text(response) -> str | None:
    """Safely pull plain text out of a raw Gemini response (may be None if it's tool-calls-only)."""
    try:
        text = response.text
        return text.strip() if text else None
    except Exception:
        # response.text raises if the response contains only function calls.
        parts_text = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                t = getattr(part, "text", None)
                if t:
                    parts_text.append(t)
        return "".join(parts_text).strip() or None
