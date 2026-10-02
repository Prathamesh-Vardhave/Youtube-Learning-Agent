# YouTube Learning Agent

Paste a YouTube link, watch the video, and chat with an AI agent that's grounded in the video's
transcript via retrieval-augmented generation (RAG). The agent can search the transcript,
locate timestamps, and generate an on-demand multiple-choice quiz -- deciding for itself which
tool (if any) to use for a given message.

## Features

- **Any YouTube URL format**: `youtube.com/watch?v=...` (including `&list=`, `&index=` playlist
  params), `youtu.be/...` (including `?si=` share tokens), `youtube.com/shorts/...`,
  `youtube.com/embed/...`, or a bare 11-character video ID.
- **Transcript RAG pipeline**: fetch transcript -> clean -> chunk (with timestamp ranges
  preserved) -> embed with `sentence-transformers` -> store in a per-video ChromaDB collection.
- **Agentic chat**: Gemini function calling over three tools -- `search_transcript`,
  `get_timestamp`, `generate_quiz` -- the model chooses when (and whether) to call them.
  Answers cite timestamps, which render as clickable "jump to" buttons that reposition the
  embedded player.
- **Quiz flow**: pick difficulty (Easy/Medium/Hard) and question count, generate a
  transcript-grounded MCQ quiz, take it one question at a time, then see your score,
  percentage, and per-question explanations, with a **Retake Quiz** option.
- **Graceful failure**: disabled/missing transcripts, invalid URLs, and LLM/JSON parsing
  hiccups all produce readable error messages instead of stack traces.

## Project structure

```
youtube-learning-agent/
├── app.py                     # Streamlit entrypoint + session-state page router
├── config/settings.py         # All env-driven configuration (incl. GEMINI_MODEL)
├── ui/
│   ├── video_page.py          # Video + chat page, quiz launcher
│   ├── quiz_page.py           # One-question-at-a-time quiz flow
│   └── results_page.py        # Score, breakdown, retake
├── rag/
│   ├── transcript.py          # youtube-transcript-api wrapper
│   ├── chunking.py            # Timestamp-preserving chunking
│   ├── embeddings.py          # sentence-transformers wrapper
│   ├── vectorstore.py         # ChromaDB persistent client, per-video collections
│   └── retriever.py           # ingest_video / search_transcript / find_best_timestamp
├── agent/
│   ├── agent.py                # ChatAgent: Gemini function-calling loop
│   ├── prompts.py              # Agent system prompt
│   └── tools/
│       ├── rag_tool.py         # search_transcript tool
│       ├── timestamp_tool.py   # get_timestamp tool
│       └── quiz_tool.py        # generate_quiz tool (chat-triggered)
├── llm/gemini.py               # google-generativeai wrapper (text/JSON/tool calling)
├── quiz/
│   ├── models.py               # Pydantic Quiz / QuizQuestion / QuizResult
│   ├── generator.py            # Gemini structured-JSON quiz generation
│   └── evaluator.py            # Scoring
├── utils/
│   ├── youtube.py               # URL parsing, timestamp formatting
│   └── helpers.py               # Text cleaning, JSON parsing, hashing
├── data/chroma/                 # Local ChromaDB persistent store (gitignored contents)
├── requirements.txt
├── Dockerfile
├── .env.example
└── .gitignore
```

## Setup (local)

1. **Python 3.11+** recommended.

2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy the environment template and add your Gemini API key
   (get one at https://aistudio.google.com/apikey):

   ```bash
   cp .env.example .env
   # then edit .env and set GEMINI_API_KEY=...
   ```

4. Run the app from the project root:

   ```bash
   streamlit run app.py
   ```

5. Open the URL Streamlit prints (default `http://localhost:8501`), paste a YouTube URL, and go.

### Configuration

All configuration lives in `config/settings.py`, driven by environment variables (see
`.env.example` for the full list). The most relevant:

| Variable              | Default             | Purpose                                              |
|------------------------|---------------------|-------------------------------------------------------|
| `GEMINI_API_KEY`       | *(required)*        | Your Gemini API key.                                  |
| `GEMINI_MODEL`         | `gemini-2.0-flash`  | Flash model used for chat/agent + quiz generation.    |
| `EMBEDDING_MODEL`      | `all-MiniLM-L6-v2`  | sentence-transformers model for transcript embeddings.|
| `CHROMA_PERSIST_DIR`   | `data/chroma`       | Where the local Chroma vector store persists.         |
| `RETRIEVER_TOP_K`      | `5`                 | Chunks retrieved per RAG query.                       |

If Google ships a newer Gemini Flash model, just update `GEMINI_MODEL` in `.env` -- no code
changes needed.

## Docker

Build and run:

```bash
docker build -t youtube-learning-agent .
docker run --rm -p 8501:8501 \
  --env-file .env \
  -v yt_agent_chroma:/app/data/chroma \
  youtube-learning-agent
```

Then open `http://localhost:8501`.

- The `-v yt_agent_chroma:/app/data/chroma` volume persists the vector store across container
  restarts so previously-watched videos don't need to be re-embedded.
- Never bake your `.env` file into the image; it's passed at runtime via `--env-file` and is
  already excluded via `.gitignore` / not copied by the `Dockerfile` (the `COPY . .` step copies
  the repo, but `.env` should never be committed to the repo in the first place).

## How it works

1. **URL -> video ID**: `utils/youtube.py` parses every common YouTube URL shape, stripping
   `?si=` share tokens, `&list=`/`&index=` playlist params, etc., down to the 11-character ID.
2. **Transcript fetch**: `rag/transcript.py` calls `youtube-transcript-api`, tolerating both the
   0.6.x and 1.x API surfaces, and raises a friendly `TranscriptUnavailableError` for
   disabled/missing transcripts or unavailable videos.
3. **Chunk + embed + store**: `rag/chunking.py` merges the raw (few-second) transcript segments
   into ~800-character chunks (configurable), each tagged with its start/end time. Each chunk is
   embedded (`rag/embeddings.py`) and upserted into a per-video ChromaDB collection
   (`rag/vectorstore.py`), so the same video is never re-embedded twice.
4. **Chat**: `agent/agent.py` starts a Gemini chat session configured with three tools. On each
   user message, Gemini decides whether to call `search_transcript`, `get_timestamp`,
   `generate_quiz`, more than one, or none -- the app executes whichever function calls Gemini
   requests and feeds the results back until Gemini produces a final answer.
5. **Quiz**: either via the chat tool or the "Take Quiz on This Video" panel, `quiz/generator.py`
   prompts Gemini (constrained to JSON output) to produce transcript-grounded MCQs at the chosen
   difficulty/count, attaches a best-match timestamp to each question via a follow-up semantic
   search, and hands a validated `quiz.models.Quiz` to the UI.
6. **Quiz UI**: `ui/quiz_page.py` walks one question at a time; on submit, `quiz/evaluator.py`
   scores the attempt and `ui/results_page.py` shows the score, percentage, and a
   correct/incorrect breakdown with explanations and "Retake Quiz".

## Troubleshooting

- **"Transcripts are disabled for this video"**: the uploader disabled captions/transcripts --
  try a different video.
- **"GEMINI_API_KEY is not set"**: make sure `.env` exists (copied from `.env.example`) and is
  in the project root, and that you're running `streamlit run app.py` from that same root.
- **Slow first request**: the first embedding call downloads the sentence-transformers model
  weights; subsequent runs are fast.
- **Re-indexing a video**: each video's transcript is only embedded once (cached by video ID in
  ChromaDB). Delete its collection under `data/chroma/` (or the `yt_agent_chroma` Docker volume)
  to force re-indexing.
