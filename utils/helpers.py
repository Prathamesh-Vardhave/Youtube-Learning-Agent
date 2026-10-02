from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def clean_transcript_text(text: str) -> str:
    """Normalize whitespace and strip filler markup that transcripts often contain."""
    text = text.replace("\n", " ")
    text = re.sub(r"\[.*?\]", " ", text)  # remove [Music], [Applause], etc.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def collection_name_for_video(video_id: str) -> str:
    """Deterministic, Chroma-safe collection name for a given video ID."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", video_id)
    return f"yt_{safe}"


def stable_hash(*parts: Any) -> str:
    """Short stable hash for building deterministic IDs (e.g. chunk IDs)."""
    joined = "||".join(str(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def safe_json_loads(text: str) -> Any:
    """
    Parse JSON possibly wrapped in markdown code fences (```json ... ```),
    which Gemini sometimes adds even when instructed not to.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def truncate(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " ..."
