from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class InvalidYouTubeURLError(ValueError):
    """Raised when a YouTube URL/ID cannot be parsed."""


def extract_video_id(url_or_id: str) -> str:
    """
    Extract an 11-character YouTube video ID from a URL or return the ID as-is
    if it already looks like one. Query parameters such as ``?si=`` (share
    tokens) and ``&list=`` (playlist ids) are stripped and ignored -- only the
    ``v`` parameter (or the path segment, for youtu.be/embed/shorts links) is
    used to determine the video ID.

    Raises:
        InvalidYouTubeURLError: if no valid video ID could be found.
    """
    if not url_or_id or not url_or_id.strip():
        raise InvalidYouTubeURLError("Please enter a YouTube URL or video ID.")

    candidate = url_or_id.strip()

    # Bare video ID pasted directly.
    if _VIDEO_ID_RE.match(candidate):
        return candidate

    # Ensure urlparse treats it as a URL even without a scheme.
    parse_target = candidate if "//" in candidate else f"//{candidate}"
    parsed = urlparse(parse_target, scheme="https")
    host = (parsed.netloc or "").lower().replace("www.", "").replace("m.", "")
    path = parsed.path or ""

    video_id: str | None = None

    if host in {"youtu.be"}:
        # https://youtu.be/VIDEO_ID?si=...
        segments = [seg for seg in path.split("/") if seg]
        if segments:
            video_id = segments[0]

    elif host in {"youtube.com", "youtube-nocookie.com"}:
        if path == "/watch":
            query = parse_qs(parsed.query)
            values = query.get("v")
            if values:
                video_id = values[0]
        elif path.startswith("/embed/"):
            video_id = path.split("/embed/", 1)[1].split("/")[0]
        elif path.startswith("/shorts/"):
            video_id = path.split("/shorts/", 1)[1].split("/")[0]
        elif path.startswith("/live/"):
            video_id = path.split("/live/", 1)[1].split("/")[0]
        elif path == "/watch/":
            query = parse_qs(parsed.query)
            values = query.get("v")
            if values:
                video_id = values[0]

    if video_id:
        # Strip any trailing query-string junk that slipped through and validate.
        video_id = video_id.split("?")[0].split("&")[0]
        if _VIDEO_ID_RE.match(video_id):
            return video_id

    raise InvalidYouTubeURLError(
        f"Could not extract a valid YouTube video ID from: {url_or_id!r}. "
        "Supported formats: youtube.com/watch?v=..., youtu.be/..., "
        "youtube.com/shorts/..., youtube.com/embed/..., or a bare video ID."
    )


def build_watch_url(video_id: str) -> str:
    """Canonical watch URL for a video ID (used for embedding / links)."""
    return f"https://www.youtube.com/watch?v={video_id}"


def build_embed_url(video_id: str, start_seconds: int | None = None) -> str:
    """Embeddable player URL, optionally seeked to a start time."""
    url = f"https://www.youtube.com/embed/{video_id}"
    if start_seconds:
        url += f"?start={int(start_seconds)}"
    return url


def format_timestamp(seconds: float) -> str:
    """Format seconds as H:MM:SS (or M:SS if under an hour)."""
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
