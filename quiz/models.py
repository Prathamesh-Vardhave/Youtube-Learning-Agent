from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Difficulty = Literal["easy", "medium", "hard"]


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int
    explanation: str
    timestamp: str | None = None
    timestamp_seconds: int | None = None

    @field_validator("correct_index")
    @classmethod
    def index_in_range(cls, v: int, info) -> int:
        options = info.data.get("options")
        if options is not None and not (0 <= v < len(options)):
            raise ValueError(f"correct_index {v} out of range for {len(options)} options")
        return v

    @property
    def correct_answer(self) -> str:
        return self.options[self.correct_index]


class Quiz(BaseModel):
    video_id: str
    difficulty: Difficulty
    questions: list[QuizQuestion]

    @property
    def num_questions(self) -> int:
        return len(self.questions)


class QuestionResult(BaseModel):
    question: QuizQuestion
    selected_index: int | None
    is_correct: bool


class QuizResult(BaseModel):
    video_id: str
    difficulty: Difficulty
    results: list[QuestionResult]

    @property
    def score(self) -> int:
        return sum(1 for r in self.results if r.is_correct)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def percentage(self) -> float:
        if not self.total:
            return 0.0
        return round(100.0 * self.score / self.total, 1)
