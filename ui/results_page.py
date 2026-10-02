from __future__ import annotations

import streamlit as st

from quiz.generator import generate_quiz


def render() -> None:
    result = st.session_state.get("quiz_result")
    if result is None:
        st.warning("No quiz results to show yet.")
        if st.button("⬅ Back to video"):
            st.session_state.page = "video"
            st.rerun()
        return

    st.title("📊 Quiz Results")

    score, total, pct = result.score, result.total, result.percentage
    st.metric("Score", f"{score} / {total}", f"{pct}%")

    if pct >= 80:
        st.success("Great work! You've got a strong grasp of this video.")
    elif pct >= 50:
        st.info("Decent effort -- review the explanations below to fill the gaps.")
    else:
        st.warning("Looks like this video's content needs another pass. Check the explanations below.")

    st.divider()
    st.subheader("Question breakdown")

    for i, qr in enumerate(result.results, start=1):
        q = qr.question
        icon = "✅" if qr.is_correct else "❌"
        with st.expander(f"{icon} Q{i}. {q.question}", expanded=not qr.is_correct):
            selected_text = q.options[qr.selected_index] if qr.selected_index is not None else "(no answer)"
            st.write(f"**Your answer:** {selected_text}")
            if not qr.is_correct:
                st.write(f"**Correct answer:** {q.correct_answer}")
            st.write(f"**Explanation:** {q.explanation}")
            if q.timestamp:
                if st.button(f"▶ Jump to {q.timestamp}", key=f"result_jump_{i}"):
                    st.session_state.video_start_time = q.timestamp_seconds or 0
                    st.session_state.page = "video"
                    st.rerun()

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔁 Retake Quiz (same settings)", type="primary"):
            with st.spinner("Generating a fresh quiz..."):
                try:
                    quiz = generate_quiz(
                        result.video_id,
                        difficulty=result.difficulty,
                        num_questions=result.total,
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not generate a new quiz: {exc}")
                    return
            st.session_state.active_quiz = quiz
            st.session_state.quiz_current_index = 0
            st.session_state.quiz_answers = [None] * quiz.num_questions
            st.session_state.quiz_result = None
            st.session_state.page = "quiz"
            st.rerun()
    with col2:
        if st.button("⬅ Back to video"):
            st.session_state.active_quiz = None
            st.session_state.quiz_result = None
            st.session_state.page = "video"
            st.rerun()
