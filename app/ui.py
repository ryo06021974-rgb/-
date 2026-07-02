import random
import re

import pandas as pd
import streamlit as st

from app.charts import build_radar_chart
from app.config import PROJECT_ROOT, is_auth_required, ordered_abilities
from app.scoring import build_result, build_result_record
from app.storage import append_result_to_csv


# Streamlit 画面描画


def initialize_session_state():
    """Streamlit のセッション状態を初期値で初期化する。

    既にキーが存在する場合は上書きしない（ページ再描画時の状態保持のため）。
    初期化するキー: answers / is_answered / user_info / is_logged_in / result_saved
    """
    defaults = {
        "answers": {},
        "is_answered": False,
        "user_info": {},
        "is_logged_in": False,
        "result_saved": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:#このif文を使うことでページ再描画時の状態保持がされる
            st.session_state[key] = value


def is_valid_email(value):
    """メールアドレスの形式として有効かどうかを返す。

    Args:
        value (str): 検証する文字列。

    Returns:
        bool: メールアドレス形式に一致する場合 True。
    """
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def read_analytics_csv(source):
    last_error = None
    for encoding in ("utf-8-sig", "cp932"):
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
        except Exception as error:
            st.warning("CSVを読み込めませんでした。ファイル形式と文字コードを確認してください。")
            st.caption(str(error))
            return None

    st.warning("CSVを読み込めませんでした。ファイル形式と文字コードを確認してください。")
    st.caption(str(last_error))
    return None


def normalize_analytics_df(config, analytics_df):
    numeric_columns = {"overall_score", "overall_level_order"}
    for ability in ordered_abilities(config):
        numeric_columns.add(f"{ability['id']}_score")

    for metric in config["analytics_metrics"]:
        calculation = metric.get("calculation")
        if calculation in {"mean", "group_mean", "below_rate"}:
            column = metric.get("column")
            if column:
                numeric_columns.add(column)

    for column in numeric_columns:
        if column in analytics_df:
            analytics_df[column] = pd.to_numeric(analytics_df[column], errors="coerce")

    return analytics_df


def render_question_form(config):
    """設問フォームを描画し、回答送信時にセッション状態を更新する。

    shuffle_questions が True の場合、初回のみ設問順をシャッフルして session_state に保存する。
    全問回答済みであれば is_answered を True にして画面を再描画する。

    Args:
        config (dict): JSONから読み込んだ設定情報。
    """
    answer_options = {option["id"]: option for option in config["answer_options"]}
    option_ids = [option["id"] for option in config["answer_options"]]
    question_by_id = {question["id"]: question for question in config["questions"]}

    if "question_order" not in st.session_state:
        question_order = [question["id"] for question in config["questions"]]
        if config["app"].get("shuffle_questions", False):
            random.shuffle(question_order)
        st.session_state.question_order = question_order
#問題の順番を確定させる
    with st.form("diagnosis_form"):
        st.subheader("設問")

        for index, question_id in enumerate(st.session_state.question_order, start=1):
            question = question_by_id[question_id]#それぞれの問題番号に対応するquestionの概要が出てくる
            st.radio(
                f"{index}. {question['text']}",
                option_ids,
                format_func=lambda option_id: answer_options[option_id]["label"],
                index=None,
                key=f"answer_{question_id}", #Streamlitが自動でst.session_state["answer_Q01"]="A4"を保存する
            )#ここで問題番号と回答内容が辞書で格納される

        submitted = st.form_submit_button("診断する", type="primary")

    if submitted:
        answers = {
            question_id: st.session_state.get(f"answer_{question_id}")
            for question_id in st.session_state.question_order
        }#ここで設問番号と回答内容を辞書で対応させる　

        unanswered_ids = [
            question_id
            for question_id, option_id in answers.items()
            if option_id is None
        ]
        if unanswered_ids:
            st.warning("すべての設問に回答してください。")
            st.stop()

        st.session_state.answers = answers
        st.session_state.is_answered = True
        st.session_state.is_logged_in = not is_auth_required(config)
        st.session_state.user_info = {}
        st.session_state.result_saved = False
        if not is_auth_required(config):
            st.session_state.result = build_result(config, answers, {})
        st.rerun()


def render_auth_form(config):
    """入力者情報フォームを描画し、認証完了後にセッション状態を更新する。

    必須項目の未入力・メールアドレス形式エラー・同意チェック未了を検証する。
    バリデーション通過後は build_result() を実行して result をセッションに保存し再描画する。

    Args:
        config (dict): JSONから読み込んだ設定情報。auth キーを使用する。
    """
    auth_config = config.get("auth", {})
    fields = auth_config.get("fields", [])
    consent_config = auth_config.get("consent", {})

    st.subheader("入力者情報")
    st.write("診断結果を表示する前に、入力者情報の登録が必要です。")

    with st.form("auth_form"):
        user_info = {}
        columns = st.columns(2)

        for index, field in enumerate(fields):
            key = f"auth_{field['id']}"
            column = columns[index % len(columns)]
            label = field["label"]
            if field.get("required", False):
                label = f"{label} *"

            with column:
                user_info[field["id"]] = st.text_input(
                    label,
                    key=key,
                    placeholder="必須" if field.get("required", False) else "",
                ).strip()#user_info["name"] = "山田太郎"みたいになる

        consent_given = True
        if consent_config.get("enabled", False):
            consent_given = st.checkbox(
                consent_config["label"],
                key="auth_consent",
            )

        submitted = st.form_submit_button("結果を見る", type="primary")

    if not submitted:
        return

    missing_fields = [
        field["label"]
        for field in fields
        if field.get("required", False) and not user_info.get(field["id"], "")
    ]#つまり必須項目が未入力の場合
    if missing_fields:
        st.warning(f"必須項目を入力してください: {', '.join(missing_fields)}")
        st.stop()

    email = user_info.get("email", "")
    if email and not is_valid_email(email):
        st.warning("メールアドレスの形式を確認してください。")
        st.stop()

    if consent_config.get("required", False) and not consent_given:
        st.warning("診断結果を表示するには、保存と共有への同意が必要です。")
        st.stop()

    st.session_state.user_info = user_info
    st.session_state.is_logged_in = True
    st.session_state.result = build_result(
        config,
        st.session_state.answers,
        user_info,
    )
    st.session_state.result_saved = False
    st.rerun()


def render_result(config, result):
    """診断結果画面を描画する。

    診断タイプ・総合スコア・レベル・レーダーチャート・能力別スコア・レベル判定・
    注意コメント・おすすめアクション・CSV出力・組織分析・再診断ボタンを表示する。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        result (dict): build_result() が返す診断結果辞書。
    """
    ability_by_id = {ability["id"]: ability for ability in config["abilities"]}
    type_names = [diagnosis_type["name"] for diagnosis_type in result["diagnosis_types"]]
    type_title = " × ".join(type_names)

    st.subheader("診断タイプ")
    if len(type_names) > 1:
        st.success(f"{type_title} の複合タイプ")
    else:
        st.success(type_title)

    st.subheader("タイプ概要")
    for diagnosis_type in result["diagnosis_types"]:
        st.write(f"**{diagnosis_type['name']}**")
        st.write(diagnosis_type["summary"])

    st.subheader("総合スコア")
    st.metric("総合スコア", f"{result['overall_score']} / 100")

    st.subheader("総合レベル")
    st.metric(
        "総合レベル",
        f"{result['overall_level']['label']} {result['overall_level']['name']}",
    )
    st.caption(result["overall_level"]["description"])

    st.subheader(config["radar_chart"]["title"])
    st.plotly_chart(
        build_radar_chart(config, result["ability_scores"]),
        use_container_width=True,
    )

    st.subheader("能力別スコア")
    score_rows = []
    for ability in ordered_abilities(config):
        ability_id = ability["id"]
        score_rows.append(
            {
                "能力": ability["name"],
                "得点": result["ability_raw_scores"][ability_id],
                "満点": result["ability_max_scores"][ability_id],
                "スコア": result["ability_scores"][ability_id],
                "概要": ability["description"],
            }
        )
    st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)

    st.subheader("能力別レベル判定")
    level_rows = []
    for ability in ordered_abilities(config):
        ability_id = ability["id"]
        level = result["ability_levels"][ability_id]
        level_rows.append(
            {
                "能力": ability["name"],
                "レベル": f"{level['label']} {level['name']}",
                "説明": level["description"],
            }
        )
    st.dataframe(pd.DataFrame(level_rows), use_container_width=True, hide_index=True)

    st.subheader("注意コメント")
    if result["warnings"]:
        for warning in result["warnings"]:
            st.warning(
                f"{warning['ability_name']}（{warning['score']}点）: {warning['message']}"
            )
    else:
        st.info("大きな注意コメントはありません。現在の強みを維持しながら活用範囲を広げましょう。")

    st.subheader("おすすめアクション")
    actions = [result["overall_level"]["next_action"]]
    for diagnosis_type in result["diagnosis_types"]:
        actions.extend(diagnosis_type["recommended_actions"])

    for action in dict.fromkeys(actions):
        st.write(f"- {action}")

    st.subheader("CSV出力")
    record = build_result_record(config, result)
    csv_df = pd.DataFrame([record])
    st.download_button(
        "診断結果CSVをダウンロード",
        csv_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=config["app"]["results_file"],
        mime="text/csv",
    )

    results_path = PROJECT_ROOT / config["app"]["results_file"]
    if st.button("この結果を results.csv に保存"):
        try:
            append_result_to_csv(record, results_path)
        except OSError as error:
            st.error("CSVファイルへの保存に失敗しました。")
            st.caption(str(error))
        else:
            st.success(f"{results_path} に保存しました。")

    render_analytics(config)

    if st.button("再診断する"):
        reset_diagnosis()
        st.rerun()


def render_analytics(config):
    """組織分析セクションを描画する。

    results.csv のアップロードまたはローカルファイルを読み込み、
    config["analytics_metrics"] に定義された集計（平均・件数・割合など）を表示する。
    データが存在しない場合はガイダンスメッセージを表示して終了する。

    Args:
        config (dict): JSONから読み込んだ設定情報。analytics_metrics キーを使用する。
    """
    st.subheader("組織分析")
    uploaded_file = st.file_uploader(
        "results.csvを読み込む",
        type="csv",
    )

    results_path = PROJECT_ROOT / config["app"]["results_file"]
    analytics_df = None

    if uploaded_file is not None:
        analytics_df = read_analytics_csv(uploaded_file)
    elif results_path.exists() and results_path.stat().st_size > 0:
        analytics_df = read_analytics_csv(results_path)

    if analytics_df is None or analytics_df.empty:
        st.info("診断結果CSVを保存またはアップロードすると、組織分析を表示できます。")
        return

    analytics_df = normalize_analytics_df(config, analytics_df)
    ability_by_id = {ability["id"]: ability for ability in config["abilities"]}

    for metric in config["analytics_metrics"]:
        st.write(f"**{metric['label']}**")
        st.caption(metric["description"])
        calculation = metric["calculation"]

        if calculation == "mean":
            column = metric["column"]
            if column in analytics_df:
                st.metric(metric["label"], f"{analytics_df[column].mean():.1f}")

        elif calculation == "count":
            st.metric(metric["label"], f"{len(analytics_df)}")

        elif calculation == "value_counts":
            column = metric["column"]
            if column in analytics_df:
                counts = analytics_df[column].value_counts().reset_index()
                counts.columns = [column, "count"]
                st.dataframe(counts, use_container_width=True, hide_index=True)

        elif calculation == "ability_means":
            rows = []
            for ability in ordered_abilities(config):
                column = f"{ability['id']}_score"
                if column in analytics_df:
                    rows.append(
                        {
                            "能力": ability_by_id[ability["id"]]["name"],
                            "平均スコア": round(analytics_df[column].mean(), 1),
                        }
                    )
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        elif calculation == "group_mean":
            group_by = metric["group_by"]
            column = metric["column"]
            if group_by in analytics_df and column in analytics_df:
                grouped = (
                    analytics_df.groupby(group_by, dropna=False)[column]
                    .mean()
                    .round(1)
                    .reset_index()
                )
                st.dataframe(grouped, use_container_width=True, hide_index=True)

        elif calculation == "below_rate":
            column = metric["column"]
            threshold = metric["threshold"]
            if column in analytics_df:
                rate = (analytics_df[column] < threshold).mean() * 100
                st.metric(metric["label"], f"{rate:.1f}%")

        elif calculation == "level_min_rate":
            if "overall_level_order" in analytics_df:
                level_orders = pd.to_numeric(
                    analytics_df["overall_level_order"],
                    errors="coerce",
                )
            elif "overall_level" in analytics_df:
                level_orders = analytics_df["overall_level"].astype(str).str.extract(
                    r"Lv\.?(\d+)"
                )[0]
                level_orders = pd.to_numeric(level_orders, errors="coerce")
            else:
                level_orders = None

            if level_orders is not None:
                rate = (level_orders >= metric["level_order_min"]).mean() * 100
                st.metric(metric["label"], f"{rate:.1f}%")


def reset_diagnosis():
    """診断に関連するセッション状態をすべて削除してリセットする。

    削除対象: result / answers / is_answered / user_info / is_logged_in /
    result_saved / question_order / answer_* / auth_* の各キー。
    """
    for key in list(st.session_state.keys()):
        if (
            key == "result"
            or key == "answers"
            or key == "is_answered"
            or key == "user_info"
            or key == "is_logged_in"
            or key == "result_saved"
            or key == "question_order"
            or key.startswith("answer_")
            or key.startswith("auth_")
        ):
            del st.session_state[key]
