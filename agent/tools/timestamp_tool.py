"""
Agent tool: find the single most relevant timestamp in the video for a
described moment or topic ("when does X happen").
"""
from __future__ import annotations

from rag.retriever import find_best_timestamp

_ACTIVE_VIDEO_ID: str | None = None


def bind_video(video_id: str) -> None:
    global _ACTIVE_VIDEO_ID
    _ACTIVE_VIDEO_ID = video_id


def get_timestamp(description: str) -> str:
    """Find the timestamp in the video where a described moment or topic occurs.

    Use this tool when the user asks *when* something happens in the video
    (e.g. "when do they talk about pricing", "what time does the demo
    start"), rather than asking to explain or summarize content.

    Args:
        description: A natural-language description of the moment or topic
            to locate (e.g. "the part about pricing tiers").

    Returns:
        A short string with the formatted timestamp (e.g. "12:47") and the
        matching transcript excerpt, or a message saying nothing matched.
    """
    if not _ACTIVE_VIDEO_ID:
        return "No video is currently loaded."

    result = find_best_timestamp(_ACTIVE_VIDEO_ID, description)
    if not result:
        return "Could not find a matching moment in this video's transcript."

    return f"Timestamp {result['timestamp']} (seconds={result['timestamp_url_seconds']}): \"{result['text']}\""
