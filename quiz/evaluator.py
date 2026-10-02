from __future__ import annotations

from quiz.models import Quiz, QuestionResult, QuizResult


def evaluate_quiz(quiz: Quiz, answers: list[int | None]) -> QuizResult:
    """
    Build a QuizResult from a quiz and the user's selected option index per
    question (None means unanswered / skipped -> counted as incorrect).
    """
    if len(answers) != len(quiz.questions):
        raise ValueError(
            f"Expected {len(quiz.questions)} answers, got {len(answers)}."
        )

    results = []
    for question, selected in zip(quiz.questions, answers):
        is_correct = selected is not None and selected == question.correct_index
        results.append(
            QuestionResult(question=question, selected_index=selected, is_correct=is_correct)
        )

    return QuizResult(video_id=quiz.video_id, difficulty=quiz.difficulty, results=results)
