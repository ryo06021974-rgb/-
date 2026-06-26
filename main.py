import streamlit as st

from app.config import is_auth_required, is_storage_required_before_result, load_config, validate_config
from app.scoring import build_result
from app.storage import save_result_to_storage
from app.ui import initialize_session_state, render_auth_form, render_question_form, render_result, reset_diagnosis


#エントリーポイント


config = load_config()

st.set_page_config(
    page_title=config["app"]["title"],
    page_icon="🤖",
    layout="wide",
)

try:
    validate_config(config)
except ValueError as error:    
    st.error(f"設定ファイルに問題があります: {error}")
    st.stop()

initialize_session_state()

st.title(config["app"]["title"])
st.write(config["app"]["description"])

if not st.session_state.is_answered:
    render_question_form(config)
elif is_auth_required(config) and not st.session_state.is_logged_in:
    render_auth_form(config)
else:
    if "result" not in st.session_state:
        st.session_state.result = build_result(
            config,
            st.session_state.answers,
            st.session_state.user_info,
        )

    if is_storage_required_before_result(config) and not st.session_state.result_saved:
        try:
            save_result_to_storage(config, st.session_state.result)
        except RuntimeError as error:
            st.error("診断結果の保存に失敗しました。時間をおいて再度お試しください。")
            st.caption(str(error))
            if st.button("保存を再試行"):
                st.rerun()
            if st.button("最初からやり直す"):
                reset_diagnosis()
                st.rerun()
            st.stop()

        st.session_state.result_saved = True

    render_result(config, st.session_state.result)
