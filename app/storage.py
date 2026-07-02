import csv
from pathlib import Path

import streamlit as st

from app.scoring import build_result_record


#   CSV / Spreadsheet 保存



def append_result_to_csv(record, path):#recordはこの下のほうの関数で定義される
    """診断結果レコードをCSVファイルに追記する。

    ファイルが存在しない、または空の場合はヘッダー行も書き込む。

    Args:
        record (dict): build_result_record() が返すフラットなレコード辞書。
        path (Path): 書き込み先CSVファイルのパス。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    fieldnames = list(record.keys())

    if not write_header:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            existing_header = reader.fieldnames or []
            rows = list(reader)

        fieldnames = existing_header + [
            column for column in record.keys() if column not in existing_header
        ]
        if fieldnames != existing_header:
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow({column: row.get(column, "") for column in fieldnames})

    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)#list(record.keys())でキーをリストでまとめ、DictWriterでそのバリューを読み込む
        if write_header:#もし最初の行であればヘッダーとしてキーを最初の行に入れる
            writer.writeheader()
        writer.writerow({column: record.get(column, "") for column in fieldnames})


def get_google_service_account_info():
    """Streamlit secrets からGoogleサービスアカウント情報を取得する。

    "gcp_service_account" または "google_service_account" のキーを順に探す。

    Returns:
        dict: サービスアカウントの認証情報辞書。

    Raises:
        RuntimeError: どちらのキーも secrets に存在しない場合。
    """
    for key in ("gcp_service_account", "google_service_account"):
        if key in st.secrets:
            return dict(st.secrets[key])

    raise RuntimeError(
        "Googleスプレッドシート保存用の認証情報が設定されていません。"
        ".streamlit/secrets.toml に gcp_service_account を設定してください。"
    )
#streamlitのsecrets.toml.exampleにあるgcp_service_accountの情報を自書としてPythonに読み込ませる

def get_or_create_worksheet(client, storage_config, column_count):
    """指定のスプレッドシートからワークシートを取得し、なければ新規作成する。

    spreadsheet_id が設定されていればIDで開き、なければ名前で検索する。
    ワークシートが存在しない場合は新規作成する。

    Args:
        client (gspread.Client): 認証済みの gspread クライアント。
        storage_config (dict): config["storage"] のストレージ設定。
        column_count (int): 新規ワークシート作成時の列数。

    Returns:
        gspread.Worksheet: 対象のワークシートオブジェクト。

    Raises:
        RuntimeError: スプレッドシートが見つからない場合。
    """
    import gspread

    spreadsheet_id = storage_config.get("spreadsheet_id", "")
    spreadsheet_name = storage_config["spreadsheet_name"]
    worksheet_name = storage_config["worksheet_name"]
#storage.jsonから取得する
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

    try:#ワークシートは一つのスプレットシートに複数存在するシートのこと
        return spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=1000,
            cols=max(column_count, 1),
        )


def ensure_worksheet_header(worksheet, header):#headerはこの後の関数で出てくる
    """ワークシートのヘッダー行を確認し、不足列があれば追記する。

    ヘッダーが空の場合は新規書き込み、既存ヘッダーに含まれない列は末尾に追加する。

    Args:
        worksheet (gspread.Worksheet): 対象のワークシート。
        header (list[str]): 期待するヘッダー列名のリスト。

    Returns:
        list[str]: 更新後の実際のヘッダー列名リスト。
    """
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
    """診断結果をGoogleスプレッドシートに保存する。

    サービスアカウント認証でスプレッドシートに接続し、ワークシートへ1行追記する。
    ヘッダーが不足している場合は自動で補完する。

    Args:
        config (dict): JSONから読み込んだ設定情報。storage キーを使用する。
        result (dict): build_result() が返す診断結果辞書。

    Raises:
        RuntimeError: gspread / google-auth が未インストール、または認証情報が不正な場合。
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as error:
        raise RuntimeError(
            "Googleスプレッドシート保存には gspread と google-auth が必要です。"
            "requirements.txt の依存関係をインストールしてください。"
        ) from error

    try:
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
        )#証明書みたいなやつ
        client = gspread.authorize(credentials)#証明書をこれに渡して権限を得る
        worksheet = get_or_create_worksheet(
            client,
            storage_config,
            column_count=len(record),
        )
        header = ensure_worksheet_header(worksheet, list(record.keys()))#実際の入力データをもとにヘッダーを作る。上にある関数により不足したデータとかも修正された状態で
        row = [record.get(column, "") for column in header]#スプレッドシートに追加する1行分のデータをリストで作る
        worksheet.append_row(row, value_input_option="USER_ENTERED")#ワークシートに行を追加する
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"Googleスプレッドシート保存中にエラーが発生しました: {error}"
        ) from error


def save_result_to_storage(config, result):
    """設定に応じたストレージへ診断結果を保存する。

    storage.enabled が False の場合は何もしない。
    現在対応している保存先は google_spreadsheet のみ。

    Args:
        config (dict): JSONから読み込んだ設定情報。
        result (dict): build_result() が返す診断結果辞書。

    Raises:
        RuntimeError: 未対応の保存先タイプが指定された場合。
    """
    storage_config = config.get("storage", {})
    if not storage_config.get("enabled", False):
        return

    if storage_config.get("type") == "google_spreadsheet":
        save_result_to_google_spreadsheet(config, result)
        return

    raise RuntimeError(f"未対応の保存先です: {storage_config.get('type')}")
