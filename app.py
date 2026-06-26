import csv
import json
import random
import re
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


CONFIG_PATH = Path("diagnosis_config.json")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def ordered_abilities(config):
    return sorted(config["abilities"], key=lambda ability: ability.get("order", 0))


def validate_config(config):
    ability_ids = {ability["id"] for ability in config["abilities"]}
    answer_option_ids = {option["id"] for option in config["answer_options"]}
    question_ids = {question["id"] for question in config["questions"]}
    type_ids = {diagnosis_type["id"] for diagnosis_type in config["types"]}

    expected_count = config["app"]["question_count"]
    if len(config["questions"]) != expected_count:
        raise ValueError(
            f"設問数が設定値と一致しません: 設定={expected_count}, 実数={len(config['questions'])}"
        )

    if len(question_ids) != len(config["questions"]):
        raise ValueError("設問IDが重複しています。")

    for question in config["questions"]:
        if question["ability_id"] not in ability_ids:
            raise ValueError(f"未定義の能力IDがあります: {question['ability_id']}")

    for option in config["answer_options"]:
        if option["score"] < config["app"]["score_min"]:
            raise ValueError(f"回答選択肢の点数が下限未満です: {option['id']}")
        if option["score"] > config["app"]["score_max"]:
            raise ValueError(f"回答選択肢の点数が上限超過です: {option['id']}")

    for rule in config["type_rules"]:
        if rule["type_id"] not in type_ids:
            raise ValueError(f"未定義のタイプIDがあります: {rule['type_id']}")
        if rule["rule_type"] == "top_ability" and rule["ability_id"] not in ability_ids:
            raise ValueError(f"未定義の能力IDがあります: {rule['ability_id']}")

    for warning in config["warnings"]:
        if warning["ability_id"] not in ability_ids:
            raise ValueError(f"未定義の注意コメント能力IDがあります: {warning['ability_id']}")

    radar_ids = config["radar_chart"]["ability_ids"]
    if any(ability_id not in ability_ids for ability_id in radar_ids):
        raise ValueError("レーダーチャートに未定義の能力IDがあります。")

    if not answer_option_ids:
        raise ValueError("回答選択肢が定義されていません。")

    auth_config = config.get("auth", {})
    if auth_config.get("enabled", False):
        field_ids = [field["id"] for field in auth_config.get("fields", [])]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("入力者情報フォームの項目IDが重複しています。")
        if auth_config.get("required_before_result", False) and not field_ids:
            raise ValueError("結果表示前ログインが有効ですが、入力者情報フォームが未定義です。")

    storage_config = config.get("storage", {})
    if storage_config.get("enabled", False):
        if storage_config.get("type") != "google_spreadsheet":
            raise ValueError("現在対応している保存先は google_spreadsheet のみです。")
        if not storage_config.get("spreadsheet_name"):
            raise ValueError("スプレッドシート名が未定義です。")
        if not storage_config.get("worksheet_name"):
            raise ValueError("ワークシート名が未定義です。")


def initialize_session_state():
    defaults = {
        "answers": {},
        "is_answered": False,
        "user_info": {},
        "is_logged_in": False,
        "result_saved": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_auth_required(config):
    auth_config = config.get("auth", {})
    return (
        auth_config.get("enabled", False)
        and auth_config.get("required_before_result", False)
    )


def is_storage_required_before_result(config):
    storage_config = config.get("storage", {})
    return (
        storage_config.get("enabled", False)
        and storage_config.get("save_timing") == "before_result_display"
    )


def is_valid_email(value):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def get_level(score, levels):
    sorted_levels = sorted(levels, key=lambda level: level["min_score"])
    selected_level = sorted_levels[0]

    for level in sorted_levels:
        if score >= level["min_score"]:
            selected_level = level

    return selected_level


def calculate_scores(config, answers):
    ability_raw_scores = {ability["id"]: 0 for ability in config["abilities"]}
    ability_max_scores = {ability["id"]: 0 for ability in config["abilities"]}
    answer_options = {option["id"]: option for option in config["answer_options"]}
    max_answer_score = max(option["score"] for option in config["answer_options"])

    for question in config["questions"]:
        ability_id = question["ability_id"]
        option_id = answers[question["id"]]

        ability_raw_scores[ability_id] += answer_options[option_id]["score"]
        ability_max_scores[ability_id] += max_answer_score

    ability_scores = {}
    for ability_id, raw_score in ability_raw_scores.items():
        max_score = ability_max_scores[ability_id]
        ability_scores[ability_id] = round(raw_score / max_score * 100, 1) if max_score else 0

    overall_score = round(sum(ability_scores.values()) / len(ability_scores), 1)

    return {
        "ability_raw_scores": ability_raw_scores,
        "ability_max_scores": ability_max_scores,
        "ability_scores": ability_scores,
        "overall_score": overall_score,
        "total_raw_score": sum(ability_raw_scores.values()),
        "total_max_score": sum(ability_max_scores.values()),
    }


def determine_types(config, overall_score, ability_scores):
    type_by_id = {diagnosis_type["id"]: diagnosis_type for diagnosis_type in config["types"]}
    range_rules = sorted(
        [rule for rule in config["type_rules"] if rule["rule_type"] == "overall_range"],
        key=lambda rule: rule.get("priority", 999),
    )

    for rule in range_rules:
        if rule["min_score"] <= overall_score <= rule["max_score"]:
            return [type_by_id[rule["type_id"]]]

    top_score = max(ability_scores.values())
    top_ability_ids = {
        ability_id
        for ability_id, score in ability_scores.items()
        if abs(score - top_score) < 0.001
    }
    top_rules = sorted(
        [rule for rule in config["type_rules"] if rule["rule_type"] == "top_ability"],
        key=lambda rule: rule.get("priority", 999),
    )

    selected_type_ids = []
    for rule in top_rules:
        if rule["ability_id"] in top_ability_ids and rule["type_id"] not in selected_type_ids:
            selected_type_ids.append(rule["type_id"])

    if not selected_type_ids:
        selected_type_ids.append(config["types"][0]["id"])

    return [type_by_id[type_id] for type_id in selected_type_ids]


def collect_warnings(config, ability_scores):
    warnings = []
    ability_by_id = {ability["id"]: ability for ability in config["abilities"]}

    for warning in config["warnings"]:
        ability_id = warning["ability_id"]
        if ability_scores[ability_id] < warning["threshold"]:
            warnings.append(
                {
                    "ability_name": ability_by_id[ability_id]["name"],
                    "score": ability_scores[ability_id],
                    "message": warning["message"],
                }
            )

    return warnings


def build_radar_chart(config, ability_scores):
    ability_by_id = {ability["id"]: ability for ability in config["abilities"]}
    ability_ids = config["radar_chart"]["ability_ids"]
    labels = [ability_by_id[ability_id]["name"] for ability_id in ability_ids]
    values = [ability_scores[ability_id] for ability_id in ability_ids]

    labels.append(labels[0])
    values.append(values[0])

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values,
                theta=labels,
                fill="toself",
                name=config["radar_chart"]["title"],
            )
        ]
    )
    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [config["radar_chart"]["min"], config["radar_chart"]["max"]],
            }
        },
        showlegend=False,
        margin={"l": 32, "r": 32, "t": 48, "b": 32},
    )

    return fig


def build_result(config, answers, profile):
    score_result = calculate_scores(config, answers)
    overall_level = get_level(score_result["overall_score"], config["levels"])
    ability_levels = {
        ability["id"]: get_level(score_result["ability_scores"][ability["id"]], config["levels"])
        for ability in config["abilities"]
    }
    diagnosis_types = determine_types(
        config,
        score_result["overall_score"],
        score_result["ability_scores"],
    )
    warnings = collect_warnings(config, score_result["ability_scores"])

    return {
        **score_result,
        "diagnosis_id": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "answers": answers,
        "profile": profile,
        "overall_level": overall_level,
        "ability_levels": ability_levels,
        "diagnosis_types": diagnosis_types,
        "warnings": warnings,
    }


def build_answers_payload(config, answers):
    answer_options = {option["id"]: option for option in config["answer_options"]}
    payload = []

    for question in config["questions"]:
        option_id = answers[question["id"]]
        option = answer_options[option_id]
        payload.append(
            {
                "question_id": question["id"],
                "ability_id": question["ability_id"],
                "answer_id": option_id,
                "answer_label": option["label"],
                "score": option["score"],
            }
        )

    return payload


def build_result_record(config, result):
    type_names = " / ".join(diagnosis_type["name"] for diagnosis_type in result["diagnosis_types"])
    overall_level = result["overall_level"]
    user_info = result.get("profile", {})

    record = {
        "diagnosis_id": result.get("diagnosis_id", str(uuid.uuid4())),
        "created_at": result.get("created_at", datetime.now().isoformat(timespec="seconds")),
        "name": user_info.get("name", ""),
        "email": user_info.get("email", ""),
        "company": user_info.get("company", ""),
        "department": user_info.get("department", ""),
        "job_type": user_info.get("job_type", ""),
        "position": user_info.get("position", ""),
        "diagnosis_type": type_names,
        "overall_score": result["overall_score"],
        "overall_level": f"{overall_level['label']} {overall_level['name']}",
    }

    for ability in ordered_abilities(config):
        ability_id = ability["id"]
        record[f"{ability_id}_score"] = result["ability_scores"][ability_id]

    record["answers_json"] = json.dumps(
        build_answers_payload(config, result["answers"]),
        ensure_ascii=False,
    )

    return record


def append_result_to_csv(record, path):
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(record.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def get_google_service_account_info():
    for key in ("gcp_service_account", "google_service_account"):
        if key in st.secrets:
            return dict(st.secrets[key])

    raise RuntimeError(
        "Googleスプレッドシート保存用の認証情報が設定されていません。"
        ".streamlit/secrets.toml に gcp_service_account を設定してください。"
    )


def get_or_create_worksheet(client, storage_config, column_count):
    import gspread

    spreadsheet_id = storage_config.get("spreadsheet_id", "")
    spreadsheet_name = storage_config["spreadsheet_name"]
    worksheet_name = storage_config["worksheet_name"]

    if spreadsheet_id:
        spreadsheet = client.open_by_key(spreadsheet_id)
    else:
        try:
            spreadsheet = client.open(spreadsheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            raise RuntimeError(
                f"スプレッドシート '{spreadsheet_name}' が見つかりません。"
                "事前に Google Drive 上でスプレッドシートを作成し、"
                "config の spreadsheet_id または spreadsheet_name を正しく設定してください。"
            )

    try:
        return spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=1000,
            cols=max(column_count, 1),
        )


def ensure_worksheet_header(worksheet, header):
    existing_header = worksheet.row_values(1)
    if not existing_header:
        worksheet.update(values=[header], range_name="A1")
        return header

    missing_columns = [column for column in header if column not in existing_header]
    if missing_columns:
        updated_header = existing_header + missing_columns
        worksheet.update(values=[updated_header], range_name="A1")
        return updated_header

    return existing_header


def save_result_to_google_spreadsheet(config, result):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as error:
        raise RuntimeError(
            "Googleスプレッドシート保存には gspread と google-auth が必要です。"
            "requirements.txt の依存関係をインストールしてください。"
        ) from error

    storage_config = config["storage"]
    record = build_result_record(config, result)
    service_account_info = get_google_service_account_info()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
    worksheet = get_or_create_worksheet(
        client,
        storage_config,
        column_count=len(record),
    )
    header = ensure_worksheet_header(worksheet, list(record.keys()))
    row = [record.get(column, "") for column in header]
    worksheet.append_row(row, value_input_option="USER_ENTERED")


def save_result_to_storage(config, result):
    storage_config = config.get("storage", {})
    if not storage_config.get("enabled", False):
        return

    if storage_config.get("type") == "google_spreadsheet":
        save_result_to_google_spreadsheet(config, result)
        return

    raise RuntimeError(f"未対応の保存先です: {storage_config.get('type')}")


def render_question_form(config):
    answer_options = {option["id"]: option for option in config["answer_options"]}
    option_ids = [option["id"] for option in config["answer_options"]]
    question_by_id = {question["id"]: question for question in config["questions"]}

    if "question_order" not in st.session_state:
        question_order = [question["id"] for question in config["questions"]]
        if config["app"].get("shuffle_questions", False):
            random.shuffle(question_order)
        st.session_state.question_order = question_order

    with st.form("diagnosis_form"):
        st.subheader("設問")

        for index, question_id in enumerate(st.session_state.question_order, start=1):
            question = question_by_id[question_id]
            st.radio(
                f"{index}. {question['text']}",
                option_ids,
                format_func=lambda option_id: answer_options[option_id]["label"],
                index=None,
                key=f"answer_{question_id}",
            )

        submitted = st.form_submit_button("診断する", type="primary")

    if submitted:
        answers = {
            question_id: st.session_state.get(f"answer_{question_id}")
            for question_id in st.session_state.question_order
        }

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
                ).strip()

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
    ]
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

    results_path = Path(config["app"]["results_file"])
    if st.button("この結果を results.csv に保存"):
        append_result_to_csv(record, results_path)
        st.success(f"{results_path} に保存しました。")

    render_analytics(config)

    if st.button("再診断する"):
        reset_diagnosis()
        st.rerun()


def render_analytics(config):
    st.subheader("組織分析")
    uploaded_file = st.file_uploader(
        "results.csvを読み込む",
        type="csv",
    )

    results_path = Path(config["app"]["results_file"])
    analytics_df = None

    if uploaded_file is not None:
        analytics_df = pd.read_csv(uploaded_file)
    elif results_path.exists() and results_path.stat().st_size > 0:
        analytics_df = pd.read_csv(results_path)

    if analytics_df is None or analytics_df.empty:
        st.info("診断結果CSVを保存またはアップロードすると、組織分析を表示できます。")
        return

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
                level_orders = analytics_df["overall_level_order"]
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
