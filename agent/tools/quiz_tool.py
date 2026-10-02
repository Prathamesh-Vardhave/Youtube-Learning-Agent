"""
Agent tool: generate an MCQ quiz from the video transcript, on request,
during the chat conversation (as distinct from the dedicated "Take Quiz"
button flow, which calls quiz.generator directly).
"""
from __future__ import annotations

from typing import Callable

from quiz.generator import generate_quiz as _generate_quiz
from quiz.models import Quiz

_ACTIVE_VIDEO_ID: str | None = None
_ON_QUIZ_GENERATED: Callable[[Quiz], None] | None = None


def bind_video(video_id: str, on_quiz_generated: Callable[[Quiz], None] | None = None) -> None:
    """Bind the active video and an optional callback invoked with the generated Quiz."""
    global _ACTIVE_VIDEO_ID, _ON_QUIZ_GENERATED
    _ACTIVE_VIDEO_ID = video_id
    _ON_QUIZ_GENERATED = on_quiz_generated


def generate_quiz(difficulty: str = "medium", num_questions: int = 5) -> str:
    """Generate a multiple-choice quiz about the video's content.

    Use this tool only when the user explicitly asks to be quizzed or tested
    on the video (e.g. "quiz me on this video", "test my understanding").
    Do not use it to merely answer a question about the content.

    Args:
        difficulty: One of "easy", "medium", or "hard".
        num_questions: How many multiple-choice questions to generate
            (reasonable range: 1-15).

    Returns:
        A short confirmation message. The quiz itself is handed off to the
        UI for the user to take interactively.
    """
    if not _ACTIVE_VIDEO_ID:
        return "No video is currently loaded."

    difficulty = difficulty.lower().strip()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    num_questions = max(1, min(int(num_questions), 15))

    quiz = _generate_quiz(_ACTIVE_VIDEO_ID, difficulty=difficulty, num_questions=num_questions)

    if _ON_QUIZ_GENERATED:
        _ON_QUIZ_GENERATED(quiz)

    return (
        f"Generated a {num_questions}-question {difficulty} quiz on this video. "
        "It's ready for the user to take -- let them know they can start it below."
    )
