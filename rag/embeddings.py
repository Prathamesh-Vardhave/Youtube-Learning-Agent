from __future__ import annotations

from functools import lru_cache

from config.settings import settings


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily: sentence-transformers/torch are heavy and we don't want
    # to pay that import cost for code paths that never touch embeddings.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts, returning one vector (as a plain list) per input."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
