"""
Agent tool: semantic search over the current video's transcript.

This module exposes a plain Python function (``search_transcript``) with a
docstring and type hints, which the Gemini SDK introspects to build the
function-calling schema automatically. The active video ID is bound via
``bind_video`` before the agent runs, since Gemini tool functions can't take
extra hidden context arguments.
"""
from __future__ import annotations

from rag.retriever import search_transcript as _search_transcript

_ACTIVE_VIDEO_ID: str | None = None


def bind_video(video_id: str) -> None:
    """Set which video's transcript this tool (and other tools in this package) searches."""
    global _ACTIVE_VIDEO_ID
    _ACTIVE_VIDEO_ID = video_id


def search_transcript(query: str) -> str:
    """Semantically search the video's transcript for passages relevant to a query.

    Use this tool whenever the user asks a question about the *content* of
    the video (what was said, explained, defined, argued, demonstrated,
    etc.). Do not use it for questions unrelated to the video.

    Args:
        query: A natural-language description of what to look for in the
            video (e.g. "how does the speaker define overfitting").

    Returns:
        A formatted string listing the most relevant transcript passages,
        each prefixed with its timestamp, most relevant first. Returns a
        message saying nothing was found if the transcript has no relevant
        content.
    """
    if not _ACTIVE_VIDEO_ID:
        return "No video is currently loaded."

    results = _search_transcript(_ACTIVE_VIDEO_ID, query, top_k=5)
    if not results:
        return "No relevant passages were found in this video's transcript."

    lines = []
    for r in results:
        lines.append(f"[{r['timestamp']}] {r['text']}")
    return "\n".join(lines)
