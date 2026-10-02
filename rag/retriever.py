from __future__ import annotations

from dataclasses import dataclass

from rag import vectorstore
from rag.chunking import chunk_transcript
from rag.transcript import TranscriptSegment, TranscriptUnavailableError, fetch_transcript
from utils.youtube import format_timestamp


@dataclass
class IngestResult:
    video_id: str
    num_segments: int
    num_chunks: int
    already_indexed: bool


def ingest_video(video_id: str, force: bool = False) -> IngestResult:
    """
    Ensure a video's transcript is fetched, chunked, embedded, and stored.
    Idempotent: if the video is already indexed and ``force`` is False, this
    is a cheap no-op.

    Raises:
        TranscriptUnavailableError: if no transcript could be fetched.
    """
    if not force and vectorstore.collection_exists_and_populated(video_id):
        existing = vectorstore.get_all_chunks(video_id)
        return IngestResult(video_id=video_id, num_segments=len(existing), num_chunks=len(existing), already_indexed=True)

    segments: list[TranscriptSegment] = fetch_transcript(video_id)
    if not segments:
        raise TranscriptUnavailableError("The transcript for this video is empty.")

    chunks = chunk_transcript(video_id, segments)
    num_indexed = vectorstore.index_chunks(video_id, chunks)

    return IngestResult(
        video_id=video_id,
        num_segments=len(segments),
        num_chunks=num_indexed,
        already_indexed=False,
    )


def search_transcript(video_id: str, query: str, top_k: int = 5) -> list[dict]:
    """
    Semantic search over a video's indexed transcript. Each result includes
    the matched text, its start/end timestamps, and a formatted timestamp
    string (e.g. "4:32") ready for display or use in a citation.
    """
    results = vectorstore.query_similar(video_id, query, top_k=top_k)
    for r in results:
        r["timestamp"] = format_timestamp(r["start"])
        r["timestamp_url_seconds"] = int(r["start"])
    return results


def get_full_transcript_text(video_id: str) -> str:
    """Concatenate all indexed chunks back into one plain-text transcript (for quiz generation)."""
    chunks = vectorstore.get_all_chunks(video_id)
    return "\n".join(c["text"] for c in chunks)


def find_best_timestamp(video_id: str, query: str) -> dict | None:
    """Return the single most relevant timestamp (as a result dict) for a natural-language query."""
    results = search_transcript(video_id, query, top_k=1)
    return results[0] if results else None
