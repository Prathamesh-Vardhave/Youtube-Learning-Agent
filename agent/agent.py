from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agent.prompts import AGENT_SYSTEM_PROMPT
from agent.tools import quiz_tool, rag_tool, timestamp_tool
from llm.gemini import get_tool_model
from quiz.models import Quiz

_MAX_TOOL_ITERATIONS = 4

_TOOLS = [rag_tool.search_transcript, timestamp_tool.get_timestamp, quiz_tool.generate_quiz]


@dataclass
class AgentTurnResult:
    text: str
    tools_used: list[str] = field(default_factory=list)
    generated_quiz: Quiz | None = None


class ChatAgent:
    """A per-video chat agent. Recreate (or call bind_video) when the video changes."""

    def __init__(self, video_id: str):
        self.video_id = video_id
        self._pending_quiz: Quiz | None = None
        rag_tool.bind_video(video_id)
        timestamp_tool.bind_video(video_id)
        quiz_tool.bind_video(video_id, on_quiz_generated=self._capture_quiz)
        self._model = get_tool_model(tools=_TOOLS, system_instruction=AGENT_SYSTEM_PROMPT)

    def _capture_quiz(self, quiz: Quiz) -> None:
        self._pending_quiz = quiz

    def start_chat(self, history: list | None = None):
        """Start (or resume) a Gemini chat session. ``history`` is a list of genai Content, if resuming."""
        return self._model.start_chat(history=history or [])

    def send(self, chat_session, user_message: str) -> AgentTurnResult:
        """
        Send a user message through the chat session, handling any tool-call
        round-trips transparently, and return the final text response.
        """
        self._pending_quiz = None
        tools_used: list[str] = []

        response = chat_session.send_message(user_message)

        for _ in range(_MAX_TOOL_ITERATIONS):
            function_calls = _extract_function_calls(response)
            if not function_calls:
                break

            tool_results = []
            for call in function_calls:
                tools_used.append(call.name)
                result_text = _dispatch_tool(call.name, call.args)
                tool_results.append(_build_function_response(call.name, result_text))

            response = chat_session.send_message(tool_results)

        final_text = _safe_text(response) or (
            "I generated that for you -- take a look below!" if self._pending_quiz else
            "I wasn't able to generate a response. Please try rephrasing your question."
        )

        return AgentTurnResult(text=final_text, tools_used=tools_used, generated_quiz=self._pending_quiz)


def _dispatch_tool(name: str, args: dict) -> str:
    fn_map: dict[str, Callable[..., str]] = {
        "search_transcript": rag_tool.search_transcript,
        "get_timestamp": timestamp_tool.get_timestamp,
        "generate_quiz": quiz_tool.generate_quiz,
    }
    fn = fn_map.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**args)
    except Exception as exc:  # noqa: BLE001
        return f"Tool '{name}' failed: {exc}"


def _extract_function_calls(response):
    calls = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            fn = getattr(part, "function_call", None)
            if fn and getattr(fn, "name", None):
                calls.append(fn)
    return calls


def _build_function_response(name: str, result_text: str):
    import google.generativeai as genai

    return genai.protos.Part(
        function_response=genai.protos.FunctionResponse(
            name=name,
            response={"result": result_text},
        )
    )


def _safe_text(response) -> str | None:
    try:
        text = response.text
        return text.strip() if text else None
    except Exception:
        chunks = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                t = getattr(part, "text", None)
                if t:
                    chunks.append(t)
        joined = "".join(chunks).strip()
        return joined or None
