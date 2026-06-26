# AI・DX能力タイプ診断アプリ

AI・DXに関する能力傾向を30問の設問で診断するWebアプリです。能力別スコア、診断タイプ、レベル判定、レーダーチャートを表示し、組織全体の分析も行えます。

## 機能

- **診断** — 30問の設問に5択で回答し、7つの能力を測定
- **結果表示** — 診断タイプ・総合スコア・能力別スコア・レーダーチャート・注意コメント・おすすめアクション
- **入力者情報フォーム** — 結果表示前に氏名・メールアドレスなどを収集（任意で有効化）
- **Googleスプレッドシート保存** — 診断結果をスプレッドシートに自動保存（任意で有効化）
- **CSV出力** — 個人の診断結果をCSVとしてダウンロード
- **組織分析** — 複数の診断結果CSVをもとに平均スコア・タイプ分布・能力別傾向を集計

## 診断能力（7項目）

| 能力 | 概要 |
| --- | --- |
| AI基礎理解 | AIの特徴、得意・不得意、基本的な活用場面を理解する力 |
| ツール活用力 | ChatGPTなどのAI・デジタルツールを業務で活用する力 |
| 業務課題発見力 | 業務のムダや課題を発見し、改善の方向性を考える力 |
| データ活用力 | データを読み取り、判断や改善に活かす力 |
| DX企画力 | DX導入の目的、効果、進め方を設計する力 |
| リスク管理能力 | 情報漏えい、著作権、誤情報、セキュリティに注意する力 |
| 組織推進力 | 周囲を巻き込み、AI・DX活用をチームや組織に広げる力 |

## ファイル構成

```
.
├── app.py                   # メインアプリケーション
├── diagnosis_config.json    # 診断設定（設問・タイプ・レベル等）
├── results.csv              # 診断結果の蓄積ファイル
├── requirements.txt
├── .streamlit/
│   ├── secrets.toml         # 認証情報（Git管理外）
│   └── secrets.toml.example # secrets.tomlのテンプレート
└── SPECIFICATION.md         # 詳細仕様書
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. アプリの起動

```bash
streamlit run app.py
```

### 3. Googleスプレッドシート保存を使う場合

`diagnosis_config.json` の `storage.enabled` を `true` にし、`.streamlit/secrets.toml` にGCPサービスアカウントの認証情報を設定します。

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

サービスアカウントには、対象スプレッドシートへの編集権限を付与してください。

## diagnosis_config.json の主な設定

| キー | 説明 |
| --- | --- |
| `app` | タイトル・説明・設問数・ファイル名等 |
| `abilities` | 診断能力の定義 |
| `questions` | 設問一覧（能力IDに紐づく） |
| `answer_options` | 回答選択肢と配点 |
| `levels` | レベル判定の閾値と説明 |
| `types` | 診断タイプの定義 |
| `type_rules` | タイプ判定ロジック |
| `warnings` | 注意コメントの条件 |
| `radar_chart` | レーダーチャートの設定 |
| `auth` | 入力者情報フォームの有効化・項目定義 |
| `storage` | スプレッドシート保存の設定 |
| `analytics_metrics` | 組織分析の指標定義 |

### auth（入力者情報フォーム）

```json
"auth": {
  "enabled": true,
  "required_before_result": true,
  "fields": [
    { "id": "name", "label": "氏名", "required": true },
    { "id": "email", "label": "メールアドレス", "required": true }
  ],
  "consent": {
    "enabled": true,
    "required": true,
    "label": "入力した個人情報と診断結果が管理者に共有・保存されることに同意します"
  }
}
```

### storage（Googleスプレッドシート）

```json
"storage": {
  "enabled": true,
  "type": "google_spreadsheet",
  "spreadsheet_id": "",
  "spreadsheet_name": "AI_DX_Diagnosis_Results",
  "worksheet_name": "diagnosis_results",
  "save_timing": "before_result_display"
}
```

`spreadsheet_id` を指定するとIDで検索します。空の場合は `spreadsheet_name` で検索します。

## スコア計算

```
能力別スコア = 能力別得点 ÷ 能力別満点 × 100
総合スコア   = 7能力スコアの平均
```

## レベル判定

| レベル | 名称 | スコア範囲 |
| --- | --- | --- |
| Lv1 | 入門者 | 0〜39 |
| Lv2 | 利用者 | 40〜54 |
| Lv3 | 実践者 | 55〜69 |
| Lv4 | 推進者 | 70〜84 |
| Lv5 | 変革リーダー | 85〜100 |

## 診断タイプ（8種類）

| タイプ | 判定条件 |
| --- | --- |
| AIひよこタイプ | 総合スコアが39以下 |
| プロンプト職人タイプ | ツール活用力が最も高い |
| 業務ハッカータイプ | 業務課題発見力が最も高い |
| データ探偵タイプ | データ活用力が最も高い |
| DX設計士タイプ | DX企画力が最も高い |
| AIガーディアンタイプ | リスク管理能力が最も高い |
| 巻き込み隊長タイプ | 組織推進力が最も高い |
| 未来変革リーダータイプ | 総合スコアが85以上 |

能力スコアが同点の場合は複合タイプとして表示されます。
