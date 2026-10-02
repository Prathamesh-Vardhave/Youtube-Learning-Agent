from __future__ import annotations

from functools import lru_cache

from config.settings import settings
from rag.chunking import TranscriptChunk
from rag.embeddings import embed_query, embed_texts
from utils.helpers import collection_name_for_video


@lru_cache(maxsize=1)
def _get_client():
    import chromadb

    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def _get_collection(video_id: str):
    client = _get_client()
    name = collection_name_for_video(video_id)
    return client.get_or_create_collection(name=name, metadata={"video_id": video_id})


def collection_exists_and_populated(video_id: str) -> bool:
    """Check whether a video's transcript has already been embedded and stored."""
    try:
        collection = _get_collection(video_id)
        return collection.count() > 0
    except Exception:
        return False


def index_chunks(video_id: str, chunks: list[TranscriptChunk]) -> int:
    """
    Embed and upsert transcript chunks into the video's Chroma collection.
    Returns the number of chunks indexed.
    """
    if not chunks:
        return 0

    collection = _get_collection(video_id)
    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)

    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        embeddings=vectors,
        documents=texts,
        metadatas=[
            {"start": c.start, "end": c.end, "index": c.index, "video_id": video_id}
            for c in chunks
        ],
    )
    return len(chunks)


def query_similar(video_id: str, query: str, top_k: int | None = None) -> list[dict]:
    """
    Return the top_k transcript chunks most semantically similar to ``query``
    for the given video, each as a dict with text/start/end/score.
    """
    top_k = top_k or settings.retriever_top_k
    collection = _get_collection(video_id)
    if collection.count() == 0:
        return []

    query_vector = embed_query(query)
    n_results = min(top_k, collection.count())
    results = collection.query(query_embeddings=[query_vector], n_results=n_results)

    out = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append(
            {
                "text": doc,
                "start": meta.get("start", 0.0),
                "end": meta.get("end", 0.0),
                "index": meta.get("index", 0),
                # Chroma returns a distance (lower = more similar); expose a
                # 0-1 "similarity" score too, which is friendlier to display.
                "distance": dist,
                "similarity": max(0.0, 1.0 - dist) if dist is not None else None,
            }
        )
    return out


def get_all_chunks(video_id: str) -> list[dict]:
    """Return every stored chunk for a video, ordered by their position in the transcript."""
    collection = _get_collection(video_id)
    if collection.count() == 0:
        return []
    results = collection.get()
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    combined = [
        {"text": doc, "start": meta.get("start", 0.0), "end": meta.get("end", 0.0), "index": meta.get("index", 0)}
        for doc, meta in zip(docs, metas)
    ]
    combined.sort(key=lambda c: c["index"])
    return combined
