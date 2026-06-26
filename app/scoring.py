import json
import uuid
from datetime import datetime

from app.config import ordered_abilities



#  スコア計算・結果構築


def get_level(score, levels):
    """スコアに対応するレベルを返す。

    min_score 以上の条件を満たす最高レベルを選択する。

    Args:
        score (float): 判定するスコア値。
        levels (list[dict]): min_score を持つレベル定義のリスト。

    Returns:
        dict: スコアに対応するレベル定義。
    """
    sorted_levels = sorted(levels, key=lambda level: level["min_score"])
    selected_level = sorted_levels[0]

    for level in sorted_levels:
        if score >= level["min_score"]:
            selected_level = level

    return selected_level


def calculate_scores(config, answers):
    """回答をもとに能力スコアと総合スコアを計算する。

    各能力の生得点を集計し、能力ごとの満点に対するパーセンテージスコア（0〜100）に変換する。
    総合スコアは全能力スコアの平均値。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        answers (dict): 設問ID をキー、回答選択肢ID を値とする辞書。

    Returns:
        dict: 以下のキーを持つスコア集計結果。
            - ability_raw_scores (dict): 能力ID → 生得点
            - ability_max_scores (dict): 能力ID → 満点
            - ability_scores (dict): 能力ID → パーセンテージスコア
            - overall_score (float): 総合スコア（全能力の平均）
            - total_raw_score (int): 全能力の生得点合計
            - total_max_score (int): 全能力の満点合計
    """
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
    """総合スコアと能力スコアをもとに診断タイプを決定する。

    まず overall_range ルールで総合スコアの範囲一致を確認し、一致すればそのタイプを返す。
    一致しない場合は top_ability ルールで最高得点の能力に対応するタイプを返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        overall_score (float): 総合スコア。
        ability_scores (dict): 能力ID をキー、パーセンテージスコアを値とする辞書。

    Returns:
        list[dict]: 該当する診断タイプ定義のリスト（1件以上）。
    """
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
    """スコアが閾値を下回る能力の注意コメントを収集する。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        ability_scores (dict): 能力ID をキー、パーセンテージスコアを値とする辞書。

    Returns:
        list[dict]: 閾値未満の能力ごとの注意情報。各要素は ability_name / score / message を持つ。
    """
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


def build_result(config, answers, profile):
    """診断の全結果データを構築して返す。

    スコア計算・レベル判定・診断タイプ決定・注意コメント収集をまとめて実行し、
    一意の診断ID と作成日時を付与した辞書を返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        answers (dict): 設問ID をキー、回答選択肢ID を値とする辞書。
        profile (dict): 入力者情報（名前・メールなど）。

    Returns:
        dict: スコア・レベル・診断タイプ・注意コメント・プロフィール等を含む診断結果。
    """
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
    """回答データをCSV保存用の詳細リストに変換する。

    各設問に対し、質問ID・能力ID・回答ID・回答ラベル・スコアを付与したリストを返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        answers (dict): 設問ID をキー、回答選択肢ID を値とする辞書。

    Returns:
        list[dict]: 設問ごとの回答詳細リスト。
    """
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
    """診断結果をCSV/スプレッドシート保存用のフラットな辞書に変換する。

    診断ID・日時・プロフィール・診断タイプ・総合スコア・レベル・能力別スコア・
    回答JSON を1行のレコードとしてまとめる。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        result (dict): build_result() が返す診断結果辞書。

    Returns:
        dict: CSVの1行に対応するフラットなレコード辞書。
    """
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
