from __future__ import annotations

import streamlit as st

from agent.agent import ChatAgent
from config.settings import settings
from quiz.generator import generate_quiz
from rag.retriever import ingest_video
from rag.transcript import TranscriptUnavailableError
from utils.youtube import InvalidYouTubeURLError, extract_video_id


def _reset_for_new_video(video_id: str) -> None:
    st.session_state.video_id = video_id
    st.session_state.messages = []
    st.session_state.chat_agent = ChatAgent(video_id)
    st.session_state.chat_session = st.session_state.chat_agent.start_chat()
    st.session_state.video_start_time = 0
    st.session_state.pending_quiz = None


def _load_video(raw_input: str) -> None:
    try:
        video_id = extract_video_id(raw_input)
    except InvalidYouTubeURLError as exc:
        st.session_state.load_error = str(exc)
        return

    st.session_state.load_error = None

    with st.spinner("Fetching transcript and building the searchable index... this can take a moment."):
        try:
            result = ingest_video(video_id)
        except TranscriptUnavailableError as exc:
            st.session_state.load_error = str(exc)
            return
        except Exception as exc:  # noqa: BLE001
            st.session_state.load_error = f"Unexpected error while processing the video: {exc}"
            return

    _reset_for_new_video(video_id)
    st.session_state.ingest_info = result


def render() -> None:
    st.title("🎓 YouTube Learning Agent")
    st.caption("Paste a YouTube link, watch the video, and chat with an AI grounded in its transcript.")

    problems = settings.validate()
    if problems:
        for p in problems:
            st.error(p)
        st.stop()

    with st.form("video_form", clear_on_submit=False):
        default_url = ""
        url_input = st.text_input(
            "YouTube URL",
            value=default_url,
            placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
        )
        submitted = st.form_submit_button("Load Video", type="primary")

    if submitted and url_input.strip():
        _load_video(url_input.strip())

    if st.session_state.get("load_error"):
        st.error(st.session_state.load_error)

    video_id = st.session_state.get("video_id")
    if not video_id:
        st.info("Enter a YouTube URL above to get started.")
        return

    info = st.session_state.get("ingest_info")
    if info is not None:
        if info.already_indexed:
            st.success(f"Loaded from index -- {info.num_chunks} transcript chunks ready.")
        else:
            st.success(f"Indexed {info.num_segments} transcript segments into {info.num_chunks} searchable chunks.")

    video_col, chat_col = st.columns([3, 2], gap="large")

    with video_col:
        st.video(f"https://www.youtube.com/watch?v={video_id}", start_time=st.session_state.get("video_start_time", 0))
        _render_quiz_launcher(video_id)

    with chat_col:
        _render_chat(video_id)


def _render_chat(video_id: str) -> None:
    st.subheader("💬 Chat about this video")

    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools_used"):
                st.caption("Tools used: " + ", ".join(msg["tools_used"]))
            if msg.get("jump_seconds") is not None:
                if st.button(f"▶ Jump to {msg['jump_label']}", key=f"jump_{msg['jump_key']}"):
                    st.session_state.video_start_time = msg["jump_seconds"]
                    st.rerun()

    user_message = st.chat_input("Ask about the video, e.g. 'What does the speaker say about X?'")
    if user_message:
        st.session_state.messages.append({"role": "user", "content": user_message})
        with st.spinner("Thinking..."):
            try:
                result = st.session_state.chat_agent.send(st.session_state.chat_session, user_message)
            except Exception as exc:  # noqa: BLE001
                result = None
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"Sorry, something went wrong: {exc}"}
                )

        if result is not None:
            jump_seconds, jump_label = _extract_jump_hint(result.text)
            assistant_msg = {
                "role": "assistant",
                "content": result.text,
                "tools_used": result.tools_used,
            }
            if jump_seconds is not None:
                assistant_msg["jump_seconds"] = jump_seconds
                assistant_msg["jump_label"] = jump_label
                assistant_msg["jump_key"] = len(st.session_state.messages)
            st.session_state.messages.append(assistant_msg)

            if result.generated_quiz is not None:
                st.session_state.pending_quiz = result.generated_quiz

        st.rerun()


def _extract_jump_hint(text: str) -> tuple[int | None, str | None]:
    """Best-effort extraction of an 'M:SS' or 'H:MM:SS' timestamp mentioned in the agent's reply."""
    import re

    match = re.search(r"\b(\d{1,2}:)?(\d{1,2}):(\d{2})\b", text)
    if not match:
        return None, None
    hours = int(match.group(1)[:-1]) if match.group(1) else 0
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    total = hours * 3600 + minutes * 60 + seconds
    label = match.group(0)
    return total, label


def _render_quiz_launcher(video_id: str) -> None:
    st.divider()
    st.subheader("📝 Take Quiz on This Video")

    if st.session_state.get("pending_quiz") is not None:
        st.info("A quiz was just generated in chat -- click below to take it, or configure a new one.")
        if st.button("Take the generated quiz"):
            st.session_state.active_quiz = st.session_state.pending_quiz
            st.session_state.pending_quiz = None
            st.session_state.quiz_current_index = 0
            st.session_state.quiz_answers = [None] * st.session_state.active_quiz.num_questions
            st.session_state.page = "quiz"
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
    with col2:
        num_questions = st.number_input(
            "Number of questions", min_value=1, max_value=settings.quiz_max_questions, value=5, step=1
        )

    if st.button("Start Quiz", type="primary"):
        with st.spinner("Generating your quiz from the transcript..."):
            try:
                quiz = generate_quiz(video_id, difficulty=difficulty.lower(), num_questions=int(num_questions))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not generate the quiz: {exc}")
                return

        st.session_state.active_quiz = quiz
        st.session_state.quiz_current_index = 0
        st.session_state.quiz_answers = [None] * quiz.num_questions
        st.session_state.page = "quiz"
        st.rerun()
