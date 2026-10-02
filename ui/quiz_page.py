from __future__ import annotations

import streamlit as st

from quiz.evaluator import evaluate_quiz


def render() -> None:
    quiz = st.session_state.get("active_quiz")
    if quiz is None:
        st.warning("No active quiz. Go back and start one from the video page.")
        if st.button("⬅ Back to video"):
            st.session_state.page = "video"
            st.rerun()
        return

    idx = st.session_state.get("quiz_current_index", 0)
    total = quiz.num_questions

    st.title("📝 Quiz")
    st.caption(f"Difficulty: {quiz.difficulty.capitalize()} · Question {idx + 1} of {total}")
    st.progress((idx) / total if total else 0.0)

    question = quiz.questions[idx]
    st.subheader(question.question)

    answers = st.session_state.quiz_answers
    current_selection = answers[idx]

    choice = st.radio(
        "Choose one:",
        options=list(range(len(question.options))),
        format_func=lambda i: question.options[i],
        index=current_selection if current_selection is not None else None,
        key=f"quiz_choice_{idx}",
    )

    col_prev, col_next, col_quit = st.columns([1, 1, 1])

    with col_prev:
        if idx > 0 and st.button("⬅ Previous"):
            answers[idx] = choice
            st.session_state.quiz_current_index -= 1
            st.rerun()

    with col_quit:
        if st.button("Quit quiz"):
            st.session_state.active_quiz = None
            st.session_state.page = "video"
            st.rerun()

    with col_next:
        is_last = idx == total - 1
        label = "Submit Quiz" if is_last else "Next ➡"
        if st.button(label, type="primary"):
            if choice is None:
                st.warning("Please select an answer before continuing.")
            else:
                answers[idx] = choice
                st.session_state.quiz_answers = answers
                if is_last:
                    result = evaluate_quiz(quiz, answers)
                    st.session_state.quiz_result = result
                    st.session_state.page = "results"
                else:
                    st.session_state.quiz_current_index += 1
                st.rerun()
