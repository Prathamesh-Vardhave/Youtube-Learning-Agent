from __future__ import annotations

import streamlit as st

from ui import quiz_page, results_page, video_page

st.set_page_config(page_title="YouTube Learning Agent", page_icon="🎓", layout="wide")


def _init_session_state() -> None:
    defaults = {
        "page": "video",
        "video_id": None,
        "messages": [],
        "chat_agent": None,
        "chat_session": None,
        "video_start_time": 0,
        "load_error": None,
        "ingest_info": None,
        "pending_quiz": None,
        "active_quiz": None,
        "quiz_current_index": 0,
        "quiz_answers": [],
        "quiz_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    _init_session_state()

    page = st.session_state.get("page", "video")
    if page == "quiz":
        quiz_page.render()
    elif page == "results":
        results_page.render()
    else:
        video_page.render()


if __name__ == "__main__":
    main()
