import json
from json import JSONDecodeError
from pathlib import Path


#設定読み込み・検証


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

_CONFIG_FILES = [
    "app",
    "abilities",
    "answer_options",
    "levels",
    "types",
    "type_rules",
    "warnings",
    "radar_chart",
    "auth",
    "storage",
    "admin",
    "analytics_metrics",
    "questions",
]


def load_config():
    """
    設定ファイルを読み込む

    Returns:
        dict: 設定内容
    """
    config = {}
    for name in _CONFIG_FILES:
        path = CONFIG_DIR / f"{name}.json"
        try:
            with path.open("r", encoding="utf-8") as f:
                config.update(json.load(f))
        except FileNotFoundError as error:
            raise ValueError(f"設定ファイルが見つかりません: {path}") from error
        except JSONDecodeError as error:
            raise ValueError(f"設定ファイルのJSON形式が不正です: {path}") from error
    return config
#ここでconfigという辞書を作ることで他のファイルでconfigの内容を取り出したいときいちいちjsonを指定しなくてよくなる

def ordered_abilities(config):
    """能力リストを order キーで昇順ソートして返す。

    Args:
        config (dict): JSONから読み込んだ設定情報。

    Returns:
        list[dict]: order 値で昇順ソートされた能力リスト。order が未定義の能力は 0 として扱う。
    """
    return sorted(config["abilities"], key=lambda ability: ability.get("order", 0))


def _require_keys(item, required_keys, label):
    if not isinstance(item, dict):
        raise ValueError(f"{label} はオブジェクト形式で定義してください。")

    missing_keys = [key for key in required_keys if key not in item]
    if missing_keys:
        raise ValueError(f"{label} のキーが不足しています: {', '.join(missing_keys)}")


def _require_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} は数値で定義してください。")


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
    missing_config_keys = [name for name in _CONFIG_FILES if name not in config]
    if missing_config_keys:
        raise ValueError(f"設定キーが不足しています: {', '.join(missing_config_keys)}")

    dict_config_keys = ["app", "radar_chart", "auth", "storage", "admin"]
    for key in dict_config_keys:
        if not isinstance(config[key], dict):
            raise ValueError(f"{key} 設定はオブジェクト形式で定義してください。")

    list_config_keys = [
        "abilities",
        "answer_options",
        "levels",
        "types",
        "type_rules",
        "warnings",
        "analytics_metrics",
        "questions",
    ]
    for key in list_config_keys:
        if not isinstance(config[key], list):
            raise ValueError(f"{key} 設定はリスト形式で定義してください。")

    app_required_keys = [
        "title",
        "description",
        "question_count",
        "score_min",
        "score_max",
        "results_file",
    ]
    missing_app_keys = [key for key in app_required_keys if key not in config["app"]]
    if missing_app_keys:
        raise ValueError(f"app設定のキーが不足しています: {', '.join(missing_app_keys)}")

    radar_required_keys = ["title", "min", "max", "ability_ids"]
    missing_radar_keys = [
        key for key in radar_required_keys if key not in config["radar_chart"]
    ]
    if missing_radar_keys:
        raise ValueError(
            f"レーダーチャート設定のキーが不足しています: {', '.join(missing_radar_keys)}"
        )

    if not config["abilities"]:
        raise ValueError("能力が定義されていません。")
    if not config["answer_options"]:
        raise ValueError("回答選択肢が定義されていません。")
    if not config["levels"]:
        raise ValueError("レベルが定義されていません。")
    if not config["types"]:
        raise ValueError("診断タイプが定義されていません。")

    _require_number(config["app"]["question_count"], "app.question_count")
    _require_number(config["app"]["score_min"], "app.score_min")
    _require_number(config["app"]["score_max"], "app.score_max")
    if config["app"]["score_min"] >= config["app"]["score_max"]:
        raise ValueError("app.score_min は app.score_max より小さくしてください。")

    for ability in config["abilities"]:
        _require_keys(ability, ["id", "name", "description", "order"], "能力設定")
        _require_number(ability["order"], f"能力 '{ability['id']}' の order")

    for option in config["answer_options"]:
        _require_keys(option, ["id", "label", "score"], "回答選択肢設定")
        _require_number(option["score"], f"回答選択肢 '{option['id']}' の score")

    for level in config["levels"]:
        _require_keys(
            level,
            ["id", "label", "name", "min_score", "max_score", "description", "next_action"],
            "レベル設定",
        )
        _require_number(level["min_score"], f"レベル '{level['id']}' の min_score")
        _require_number(level["max_score"], f"レベル '{level['id']}' の max_score")
        if level["min_score"] > level["max_score"]:
            raise ValueError(f"レベル '{level['id']}' の min_score が max_score を超えています。")

    for diagnosis_type in config["types"]:
        _require_keys(
            diagnosis_type,
            ["id", "name", "summary", "recommended_actions"],
            "診断タイプ設定",
        )
        if not isinstance(diagnosis_type["recommended_actions"], list):
            raise ValueError(f"診断タイプ '{diagnosis_type['id']}' の recommended_actions はリストで定義してください。")

    for question in config["questions"]:
        _require_keys(question, ["id", "text", "ability_id", "score_type"], "設問設定")

    ability_id_list = [ability["id"] for ability in config["abilities"]]
    answer_option_id_list = [option["id"] for option in config["answer_options"]]
    question_id_list = [question["id"] for question in config["questions"]]
    type_id_list = [diagnosis_type["id"] for diagnosis_type in config["types"]]

    ability_ids = set(ability_id_list)
    answer_option_ids = set(answer_option_id_list)
    question_ids = set(question_id_list)
    type_ids = set(type_id_list)

    if len(ability_ids) != len(ability_id_list):
        raise ValueError("能力IDが重複しています。")
    if len(answer_option_ids) != len(answer_option_id_list):
        raise ValueError("回答選択肢IDが重複しています。")
    if len(type_ids) != len(type_id_list):
        raise ValueError("診断タイプIDが重複しています。")

    expected_count = config["app"]["question_count"]
    if len(config["questions"]) != expected_count:
        raise ValueError(
            f"設問数が設定値と一致しません: 設定={expected_count}, 実数={len(config['questions'])}"
        )

    if len(question_ids) != len(question_id_list):
        raise ValueError("設問IDが重複しています。")

    for question in config["questions"]:
        if question["ability_id"] not in ability_ids:
            raise ValueError(f"未定義の能力IDがあります: {question['ability_id']}")

    for option in config["answer_options"]:
        if option["score"] < config["app"]["score_min"]:
            raise ValueError(f"回答選択肢の点数が下限未満です: {option['id']}")
        if option["score"] > config["app"]["score_max"]:
            raise ValueError(f"回答選択肢の点数が上限超過です: {option['id']}")

    valid_rule_types = {"overall_range", "top_ability"}
    for rule in config["type_rules"]:
        _require_keys(rule, ["id", "rule_type", "type_id", "priority"], "タイプ判定ルール設定")
        if rule["rule_type"] not in valid_rule_types:
            raise ValueError(f"未対応のタイプ判定ルールがあります: {rule['rule_type']}")
        if rule["type_id"] not in type_ids:
            raise ValueError(f"未定義のタイプIDがあります: {rule['type_id']}")
        _require_number(rule["priority"], f"タイプ判定ルール '{rule['id']}' の priority")
        if rule["rule_type"] == "overall_range":
            _require_keys(rule, ["min_score", "max_score"], f"タイプ判定ルール '{rule['id']}'")
            _require_number(rule["min_score"], f"タイプ判定ルール '{rule['id']}' の min_score")
            _require_number(rule["max_score"], f"タイプ判定ルール '{rule['id']}' の max_score")
            if rule["min_score"] > rule["max_score"]:
                raise ValueError(f"タイプ判定ルール '{rule['id']}' の min_score が max_score を超えています。")
        if rule["rule_type"] == "top_ability":
            _require_keys(rule, ["ability_id"], f"タイプ判定ルール '{rule['id']}'")
        if rule["rule_type"] == "top_ability" and rule["ability_id"] not in ability_ids:
            raise ValueError(f"未定義の能力IDがあります: {rule['ability_id']}")

    for warning in config["warnings"]:
        _require_keys(warning, ["id", "ability_id", "threshold", "message"], "注意コメント設定")
        _require_number(warning["threshold"], f"注意コメント '{warning['id']}' の threshold")
        if warning["ability_id"] not in ability_ids:
            raise ValueError(f"未定義の注意コメント能力IDがあります: {warning['ability_id']}")

    radar_ids = config["radar_chart"]["ability_ids"]
    _require_number(config["radar_chart"]["min"], "radar_chart.min")
    _require_number(config["radar_chart"]["max"], "radar_chart.max")
    if config["radar_chart"]["min"] >= config["radar_chart"]["max"]:
        raise ValueError("radar_chart.min は radar_chart.max より小さくしてください。")
    if not radar_ids:
        raise ValueError("レーダーチャートの能力IDが定義されていません。")
    if any(ability_id not in ability_ids for ability_id in radar_ids):
        raise ValueError("レーダーチャートに未定義の能力IDがあります。")

    auth_config = config.get("auth", {})
    if auth_config.get("enabled", False):
        if auth_config.get("method") != "profile_form":
            raise ValueError("現在対応している認証方式は profile_form のみです。")
        for field in auth_config.get("fields", []):
            _require_keys(field, ["id", "label", "type", "required"], "入力者情報フォーム項目")
        field_ids = [field["id"] for field in auth_config.get("fields", [])]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("入力者情報フォームの項目IDが重複しています。")
        if auth_config.get("required_before_result", False) and not field_ids:
            raise ValueError("結果表示前ログインが有効ですが、入力者情報フォームが未定義です。")
        consent_config = auth_config.get("consent", {})
        if consent_config.get("enabled", False):
            _require_keys(consent_config, ["label", "required"], "同意チェック設定")

    valid_calculations = {
        "count",
        "mean",
        "value_counts",
        "ability_means",
        "group_mean",
        "below_rate",
        "level_min_rate",
    }
    calculation_required_keys = {
        "mean": ["column"],
        "value_counts": ["column"],
        "group_mean": ["group_by", "column"],
        "below_rate": ["column", "threshold"],
        "level_min_rate": ["level_order_min"],
    }
    for metric in config["analytics_metrics"]:
        for key in ("id", "label", "description", "calculation"):
            if key not in metric:
                raise ValueError(f"分析指標のキーが不足しています: {key}")
        if metric["calculation"] not in valid_calculations:
            raise ValueError(f"未対応の分析指標があります: {metric['calculation']}")
        for key in calculation_required_keys.get(metric["calculation"], []):
            if key not in metric:
                raise ValueError(
                    f"分析指標 '{metric['id']}' のキーが不足しています: {key}"
                )

    storage_config = config.get("storage", {})
    if storage_config.get("enabled", False):
        if storage_config.get("type") != "google_spreadsheet":
            raise ValueError("現在対応している保存先は google_spreadsheet のみです。")
        if not storage_config.get("spreadsheet_name"):
            raise ValueError("スプレッドシート名が未定義です。")
        if not storage_config.get("worksheet_name"):
            raise ValueError("ワークシート名が未定義です。")
        if storage_config.get("save_timing") != "before_result_display":
            raise ValueError("保存タイミングは before_result_display のみ対応しています。")


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
