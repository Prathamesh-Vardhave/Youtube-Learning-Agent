from __future__ import annotations

from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi

try:  # pragma: no cover - exact exception module path differs across versions
    from youtube_transcript_api import (
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )
except ImportError:  # pragma: no cover
    from youtube_transcript_api._errors import (  # type: ignore
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )


class TranscriptUnavailableError(Exception):
    """Raised when a transcript cannot be fetched for any reason, with a user-friendly message."""


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


def _segments_from_raw(raw: list[dict]) -> list[TranscriptSegment]:
    segments = []
    for item in raw:
        # FetchedTranscriptSnippet (1.x) supports attribute access; dicts (0.6.x) don't.
        if isinstance(item, dict):
            text = item.get("text", "")
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
        else:
            text = getattr(item, "text", "")
            start = float(getattr(item, "start", 0.0))
            duration = float(getattr(item, "duration", 0.0))
        if text and text.strip():
            segments.append(TranscriptSegment(text=text.strip(), start=start, duration=duration))
    return segments


def fetch_transcript(video_id: str, languages: list[str] | None = None) -> list[TranscriptSegment]:
    """
    Fetch the transcript for a video as an ordered list of TranscriptSegment.

    Tries the requested languages first (default: English variants), then
    falls back to any available manually-created transcript, then any
    available auto-generated transcript, translating to English if possible.

    Raises:
        TranscriptUnavailableError: with a human-readable reason, if no
        transcript could be obtained.
    """
    languages = languages or ["en", "en-US", "en-GB"]

    # --- Newer API (youtube-transcript-api >= 1.0): instance-based ---------
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            try:
                fetched = api.fetch(video_id, languages=languages)
                return _segments_from_raw(list(fetched))
            except Exception:
                pass  # fall through to the list()/find_transcript() path below
    except Exception:
        pass

    # --- list_transcripts / find_transcript path (works on both major versions
    #     in slightly different forms) -------------------------------------
    try:
        list_fn = getattr(YouTubeTranscriptApi, "list_transcripts", None)
        if list_fn is None:
            list_fn = getattr(YouTubeTranscriptApi(), "list", None)
        transcript_list = list_fn(video_id)

        transcript = None
        try:
            transcript = transcript_list.find_transcript(languages)
        except Exception:
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(languages)
                except Exception:
                    # Last resort: grab the first available transcript and translate it.
                    available = list(transcript_list)
                    if not available:
                        raise
                    transcript = available[0]
                    if getattr(transcript, "is_translatable", False):
                        try:
                            transcript = transcript.translate("en")
                        except Exception:
                            pass

        raw = transcript.fetch()
        return _segments_from_raw(list(raw))

    except TranscriptsDisabled as exc:
        raise TranscriptUnavailableError(
            "Transcripts are disabled for this video. Try a different video."
        ) from exc
    except NoTranscriptFound as exc:
        raise TranscriptUnavailableError(
            "No transcript is available for this video in a supported language."
        ) from exc
    except VideoUnavailable as exc:
        raise TranscriptUnavailableError(
            "This video is unavailable (private, deleted, or region-locked)."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface any other failure clearly
        raise TranscriptUnavailableError(
            f"Could not fetch a transcript for this video ({exc.__class__.__name__}: {exc})."
        ) from exc
