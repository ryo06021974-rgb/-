import json
from pathlib import Path


#　　設定読み込み・検証


CONFIG_PATH = Path("diagnosis_config.json")


def load_config():
    """
    設定ファイルを読み込む 
    
    Returns:
        dict: 設定内容
    """
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def ordered_abilities(config):
    """能力リストを order キーで昇順ソートして返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。

    Returns:
        list[dict]: order 値で昇順ソートされた能力リスト。order が未定義の能力は 0 として扱う。
    """
    return sorted(config["abilities"], key=lambda ability: ability.get("order", 0))


def validate_config(config):
    """設定ファイルの整合性を検証する。

    以下の項目を順に検証し、問題があれば ValueError を送出する。
    - 設問数が app.question_count と一致しているか
    - 設問IDに重複がないか
    - 各設問の ability_id が定義済みの能力IDか
    - 回答選択肢のスコアが score_min〜score_max の範囲内か
    - タイプルールの type_id / ability_id が定義済みか
    - 注意コメントの ability_id が定義済みか
    - レーダーチャートの ability_ids が定義済みか
    - 回答選択肢が1件以上定義されているか
    - 認証フォームの項目IDに重複がないか
    - ストレージ設定が有効な場合の必須項目が揃っているか

    Args:
        config (dict): JSONから読み込んだ設定情報。

    Raises:
        ValueError: 設定に不整合が見つかった場合。
    """
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


def is_auth_required(config):
    """結果表示前に入力者情報の認証が必要かどうかを返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。

    Returns:
        bool: auth.enabled かつ auth.required_before_result が True の場合に True。
    """
    auth_config = config.get("auth", {})
    return (
        auth_config.get("enabled", False)
        and auth_config.get("required_before_result", False)
    )


def is_storage_required_before_result(config):
    """結果表示前にストレージへの保存が必要かどうかを返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。

    Returns:
        bool: storage.enabled が True かつ storage.save_timing が "before_result_display" の場合に True。
    """
    storage_config = config.get("storage", {})
    return (
        storage_config.get("enabled", False)
        and storage_config.get("save_timing") == "before_result_display"
    )
