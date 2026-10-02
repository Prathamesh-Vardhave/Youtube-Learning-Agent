from __future__ import annotations

from config.settings import settings
from llm.gemini import generate_json
from quiz.models import Quiz, QuizQuestion
from rag import vectorstore
from rag.retriever import get_full_transcript_text
from utils.helpers import safe_json_loads, truncate
from utils.youtube import format_timestamp

_DIFFICULTY_GUIDANCE = {
    "easy": (
        "Easy: test recall of clearly-stated facts and definitions directly mentioned in the "
        "transcript. Avoid trick wording. Distractors should be clearly wrong to someone who "
        "watched the video."
    ),
    "medium": (
        "Medium: test understanding of concepts and relationships explained in the video, "
        "requiring the viewer to connect two or more points made in the transcript. "
        "Distractors should be plausible but distinguishable."
    ),
    "hard": (
        "Hard: test deeper comprehension, application, and inference based on the video's "
        "content (e.g. 'which of these follows from what the speaker said'). Distractors should "
        "be subtly wrong and require careful reasoning to eliminate."
    ),
}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "correct_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                    "source_excerpt": {
                        "type": "string",
                        "description": "A short verbatim-ish snippet from the transcript that supports the answer, used to locate a timestamp.",
                    },
                },
                "required": ["question", "options", "correct_index", "explanation"],
            },
        }
    },
    "required": ["questions"],
}


def _build_prompt(transcript_text: str, difficulty: str, num_questions: int) -> str:
    guidance = _DIFFICULTY_GUIDANCE[difficulty]
    return f"""You are an expert instructional designer creating a quiz strictly grounded in a video transcript.

TRANSCRIPT:
\"\"\"
{transcript_text}
\"\"\"

Create exactly {num_questions} multiple-choice questions about this transcript.
Difficulty level: {difficulty}. {guidance}

Rules:
- Every question and its correct answer must be fully supported by the transcript. Do not invent facts not present in it.
- Each question must have exactly 4 options, only one of which is correct.
- correct_index is the 0-based index of the correct option within "options".
- Write a 1-2 sentence explanation for why the correct answer is right.
- Include a short "source_excerpt" copied from the transcript that supports each answer, so it can be matched to a timestamp.
- Vary question phrasing and the position of the correct answer across questions -- do not always put the correct answer at index 0.
- Return ONLY JSON matching the required schema, no extra commentary."""


def _attach_timestamps(video_id: str, questions: list[QuizQuestion], raw_questions: list[dict]) -> None:
    """Best-effort: match each question's source excerpt to a transcript chunk to attach a timestamp."""
    for q, raw in zip(questions, raw_questions):
        excerpt = (raw.get("source_excerpt") or raw.get("question") or "").strip()
        if not excerpt:
            continue
        try:
            matches = vectorstore.query_similar(video_id, excerpt, top_k=1)
        except Exception:
            matches = []
        if matches:
            q.timestamp = format_timestamp(matches[0]["start"])
            q.timestamp_seconds = int(matches[0]["start"])


def generate_quiz(video_id: str, difficulty: str = "medium", num_questions: int = 5) -> Quiz:
    """
    Generate a Quiz for the given (already-indexed) video, grounded in its
    transcript, via Gemini structured JSON output.
    """
    difficulty = difficulty.lower().strip()
    if difficulty not in _DIFFICULTY_GUIDANCE:
        difficulty = "medium"
    num_questions = max(1, min(int(num_questions), settings.quiz_max_questions))

    transcript_text = get_full_transcript_text(video_id)
    if not transcript_text.strip():
        raise ValueError("This video has no indexed transcript to generate a quiz from.")

    # Gemini has a large context window, but keep the prompt bounded for cost/latency.
    transcript_text = truncate(transcript_text, max_chars=24000)

    prompt = _build_prompt(transcript_text, difficulty, num_questions)
    raw_response = generate_json(prompt, schema=_RESPONSE_SCHEMA, temperature=0.4)
    data = safe_json_loads(raw_response)

    raw_questions = data.get("questions", [])
    if not raw_questions:
        raise ValueError("The quiz generator returned no questions. Try again.")

    questions: list[QuizQuestion] = []
    for rq in raw_questions[:num_questions]:
        try:
            questions.append(
                QuizQuestion(
                    question=rq["question"],
                    options=rq["options"],
                    correct_index=int(rq["correct_index"]),
                    explanation=rq.get("explanation", ""),
                )
            )
        except Exception:
            continue  # skip malformed questions rather than failing the whole quiz

    if not questions:
        raise ValueError("Could not parse any valid questions from the model's response.")

    _attach_timestamps(video_id, questions, raw_questions[: len(questions)])

    return Quiz(video_id=video_id, difficulty=difficulty, questions=questions)
