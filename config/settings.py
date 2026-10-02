from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- Gemini / LLM -----------------------------------------------------
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    # Configurable Gemini Flash model used for both the agent (function calling)
    # and quiz generation. Override via the GEMINI_MODEL env var if Google
    # ships a newer Flash model you want to switch to.
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    gemini_temperature: float = field(default_factory=lambda: float(os.getenv("GEMINI_TEMPERATURE", "0.3")))

    # --- Embeddings / vector store ------------------------------------------
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    chroma_persist_dir: str = field(
        default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", str(PROJECT_ROOT / "data" / "chroma"))
    )

    # --- Chunking / retrieval -----------------------------------------------
    chunk_max_chars: int = field(default_factory=lambda: int(os.getenv("CHUNK_MAX_CHARS", "800")))
    chunk_overlap_chars: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP_CHARS", "150")))
    retriever_top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVER_TOP_K", "5")))

    # --- Quiz ---------------------------------------------------------------
    quiz_max_questions: int = field(default_factory=lambda: int(os.getenv("QUIZ_MAX_QUESTIONS", "15")))

    # --- Misc -----------------------------------------------------------------
    debug: bool = field(default_factory=lambda: _get_bool("DEBUG", False))

    def validate(self) -> list[str]:
        """Return a list of human-readable problems with the current config (empty = OK)."""
        problems = []
        if not self.gemini_api_key:
            problems.append(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your Gemini API key."
            )
        return problems


settings = Settings()
