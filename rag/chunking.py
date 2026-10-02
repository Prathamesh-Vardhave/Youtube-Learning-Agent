from __future__ import annotations

from dataclasses import dataclass

from config.settings import settings
from rag.transcript import TranscriptSegment
from utils.helpers import clean_transcript_text, stable_hash


@dataclass(frozen=True)
class TranscriptChunk:
    chunk_id: str
    text: str
    start: float
    end: float
    index: int

    @property
    def duration(self) -> float:
        return self.end - self.start


def chunk_transcript(
    video_id: str,
    segments: list[TranscriptSegment],
    max_chars: int | None = None,
    overlap_chars: int | None = None,
) -> list[TranscriptChunk]:
    """
    Merge consecutive transcript segments into chunks of roughly ``max_chars``
    characters, each tagged with the start/end time it spans. A small
    character overlap is carried into the next chunk so semantic search near
    a chunk boundary doesn't lose context.
    """
    max_chars = max_chars or settings.chunk_max_chars
    overlap_chars = overlap_chars or settings.chunk_overlap_chars

    if not segments:
        return []

    chunks: list[TranscriptChunk] = []
    buffer_text = ""
    buffer_start: float | None = None
    buffer_end = 0.0

    def flush(next_index: int) -> None:
        nonlocal buffer_text, buffer_start, buffer_end
        if buffer_text.strip() and buffer_start is not None:
            cid = stable_hash(video_id, next_index, buffer_start)
            chunks.append(
                TranscriptChunk(
                    chunk_id=cid,
                    text=clean_transcript_text(buffer_text),
                    start=buffer_start,
                    end=buffer_end,
                    index=next_index,
                )
            )

    for seg in segments:
        seg_text = clean_transcript_text(seg.text)
        if not seg_text:
            continue

        if buffer_start is None:
            buffer_start = seg.start

        candidate = f"{buffer_text} {seg_text}".strip()

        if len(candidate) > max_chars and buffer_text:
            flush(len(chunks))
            # Start the new buffer with a character-overlap tail of the previous chunk.
            tail = buffer_text[-overlap_chars:] if overlap_chars else ""
            buffer_text = f"{tail} {seg_text}".strip()
            buffer_start = seg.start
            buffer_end = seg.end
        else:
            buffer_text = candidate
            buffer_end = seg.end

    flush(len(chunks))

    return chunks
