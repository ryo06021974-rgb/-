import random

import pandas as pd
import streamlit as st

from events import IDEAL_TEAMS
from questions import QUESTIONS
from roles import ROLE_DESCRIPTIONS, ROLES


st.set_page_config(
    page_title="チーム役割診断",
    page_icon="🎯",
    layout="wide",
)


if "submitted" not in st.session_state:
    st.session_state.submitted = False


if "questions" not in st.session_state:
    shuffled = QUESTIONS.copy()
    random.shuffle(shuffled)
    st.session_state.questions = shuffled


if "choice_orders" not in st.session_state:
    choice_orders = []

    for question in st.session_state.questions:
        choices = list(question["choices"].items())
        random.shuffle(choices)
        choice_orders.append(choices)

    st.session_state.choice_orders = choice_orders


st.title("🎯 チーム役割診断")

st.write(
    """
24個の質問に答えることで、
あなたがチームで発揮しやすい役割を診断します。
"""
)


if not st.session_state.submitted:
    answers = []

    for index, question in enumerate(st.session_state.questions):
        choices = st.session_state.choice_orders[index]
        labels = [label for label, role in choices]

        answer = st.radio(
            f"Q{index + 1}. {question['question']}",
            labels,
            index=None,
            key=f"q{index}",
        )

        answers.append(answer)

    if st.button("診断する", type="primary"):
        if None in answers:
            st.warning("すべての質問に回答してください。")
            st.stop()

        scores = {role: 0 for role in ROLES}

        for answer, choices in zip(answers, st.session_state.choice_orders):
            choice_to_role = dict(choices)
            selected_role = choice_to_role[answer]
            scores[selected_role] += 1

        st.session_state.scores = scores
        st.session_state.submitted = True
        st.rerun()


else:
    scores = st.session_state.scores

    ranking = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_score = ranking[0][1]
    top_roles = [
        role
        for role, score in ranking
        if score == top_score
    ]

    if len(top_roles) == 1:
        role = top_roles[0]
        emoji = ROLES[role]

        st.success(f"{emoji} あなたは『{role}』タイプです！")

    else:
        text = " × ".join(
            f"{ROLES[role]} {role}"
            for role in top_roles
        )

        st.success(f"あなたは『{text}』の複合タイプです！")

    st.subheader("🏆 あなたの役割ランキング")

    total = sum(scores.values())

    for role, score in ranking:
        percent = round(score / total * 100, 1)
        st.write(f"{ROLES[role]} {role} : {score}点 / {percent}%")

    chart_data = pd.DataFrame(
        {"点数": [score for role, score in ranking]},
        index=[role for role, score in ranking],
    )

    st.bar_chart(chart_data)

    main_role = ranking[0][0]
    info = ROLE_DESCRIPTIONS[main_role]

    st.subheader(f"{ROLES[main_role]} {info['title']}")
    st.write(info["description"])

    for strength in info["strengths"]:
        st.write(f"✅ {strength}")

    if len(top_roles) > 1:
        st.subheader("同率トップの役割")

        for role in top_roles:
            info = ROLE_DESCRIPTIONS[role]

            with st.expander(f"{ROLES[role]} {info['title']}"):
                st.write(info["description"])

                for strength in info["strengths"]:
                    st.write(f"✅ {strength}")

    st.subheader("🎪 イベント別おすすめ編成")

    for event, team in IDEAL_TEAMS.items():
        with st.expander(event):
            for role, num in team.items():
                st.write(f"{ROLES[role]} {role} : {num}人")

    if st.button("もう一度診断する"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.rerun()