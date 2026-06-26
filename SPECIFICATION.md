# AI・DX能力タイプ診断アプリ 仕様書

## 1. アプリ概要

本アプリは、ユーザーが30問の設問に回答することで、AI・DXに関する能力傾向、診断タイプ、総合レベル、能力別レベルを判定するWebアプリである。

診断結果では以下を表示する。

- 診断タイプ
- タイプ概要
- 総合スコア
- 総合レベル
- 7能力のレーダーチャート
- 能力別スコア
- 能力別レベル判定
- 注意コメント
- おすすめアクション
- CSV出力
- 組織分析

## 2. 開発方針

アプリの処理ロジックと診断データを分離する。

`app.py` はJSON読み込み、設問表示、回答受付、得点集計、スコア計算、レベル判定、タイプ判定、注意コメント判定、表示処理、レーダーチャート描画、CSV出力、集計処理のみを担当する。

診断内容は `diagnosis_config.json` で管理する。

## 3. 使用技術

- Python 3.x
- Streamlit
- pandas
- plotly
- gspread
- google-auth
- json
- random

`requirements.txt`

```text
streamlit
pandas
plotly
gspread
google-auth
```

## 4. ファイル構成

```text
ai_dx_diagnosis_app/
├─ app.py
├─ diagnosis_config.json
├─ results.csv
├─ .streamlit/
│  └─ secrets.toml
└─ requirements.txt
```

## 5. 診断能力

レーダーチャートに表示する能力は以下の7項目とする。

| ID | 能力名 | 概要 |
| --- | --- | --- |
| ai_basic | AI基礎理解 | AIの特徴、得意・不得意、基本的な活用場面を理解する力 |
| tool_usage | ツール活用力 | ChatGPTなどのAI・デジタルツールを業務で活用する力 |
| business_issue | 業務課題発見力 | 業務のムダや課題を発見し、改善の方向性を考える力 |
| data_usage | データ活用力 | データを読み取り、判断や改善に活かす力 |
| dx_planning | DX企画力 | DX導入の目的、効果、進め方を設計する力 |
| risk_management | リスク管理能力 | 情報漏えい、著作権、誤情報、セキュリティに注意する力 |
| organization_drive | 組織推進力 | 周囲を巻き込み、AI・DX活用をチームや組織に広げる力 |

## 6. タイプ診断

診断タイプは以下の8種類とする。

- AIひよこタイプ
- プロンプト職人タイプ
- 業務ハッカータイプ
- データ探偵タイプ
- DX設計士タイプ
- AIガーディアンタイプ
- 巻き込み隊長タイプ
- 未来変革リーダータイプ

## 7. 設問仕様

- 設問数: 30問
- 回答形式: 5択
- 配点: 0〜4点

| 回答 | 点数 |
| --- | ---: |
| ほとんどできない | 0 |
| あまりできない | 1 |
| どちらともいえない | 2 |
| ある程度できる | 3 |
| 十分できる | 4 |

各設問は以下を持つ。

- 設問ID
- 設問本文
- 能力タグ
- カテゴリ
- サブカテゴリ
- 配点方式

## 8. 設問カテゴリ

### マインドスタンス

- 変化への適応
- コラボレーション
- 顧客・ユーザー視点

### DXリテラシー

why DXの背景:

- 社会の変化
- 顧客価値観の変化
- 競争環境の変化

what DXで活用されるデータ・技術:

- データ
- 社会におけるデータ
- データを読む・説明する
- データを扱う
- データによって判断する
- AI
- クラウド
- ハードウェア・ソフトウェア
- ネットワーク

how データ・技術の利活用:

- データ・デジタル技術の活用事例
- ツール利用
- セキュリティー
- モラル
- コンプライアンス

## 9. スコア計算

能力別スコアは、各能力に紐づく設問の合計点から算出する。

```text
能力別スコア = 能力別得点 ÷ 能力別満点 × 100
```

総合スコアは7能力スコアの平均値とする。

```text
総合スコア = 7能力スコアの平均
```

## 10. レベル判定

| レベル | 名称 | スコア範囲 | 概要 |
| --- | --- | ---: | --- |
| Lv1 | 入門者 | 0〜39 | 基礎理解や活用経験がまだ少ない段階 |
| Lv2 | 利用者 | 40〜54 | 基本的な使い方を理解し、個人で試し始めている段階 |
| Lv3 | 実践者 | 55〜69 | 業務や活動の中でAI・DXを実際に活用できる段階 |
| Lv4 | 推進者 | 70〜84 | 周囲にもAI・DX活用を広げられる段階 |
| Lv5 | 変革リーダー | 85〜100 | 組織や業務の変革を主導できる段階 |

## 11. タイプ判定

タイプ判定は、総合スコアと能力別スコアをもとに行う。

| 条件 | タイプ |
| --- | --- |
| 総合スコアが39以下 | AIひよこタイプ |
| ツール活用力が最も高い | プロンプト職人タイプ |
| 業務課題発見力が最も高い | 業務ハッカータイプ |
| データ活用力が最も高い | データ探偵タイプ |
| DX企画力が最も高い | DX設計士タイプ |
| リスク管理能力が最も高い | AIガーディアンタイプ |
| 組織推進力が最も高い | 巻き込み隊長タイプ |
| 総合スコアが85以上 | 未来変革リーダータイプ |

同点の場合は複合タイプとして表示する。

## 12. レーダーチャート

7能力を0〜100点で表示する。

- AI基礎理解
- ツール活用力
- 業務課題発見力
- データ活用力
- DX企画力
- リスク管理能力
- 組織推進力

## 13. 注意コメント

| 条件 | 注意コメント |
| --- | --- |
| リスク管理力 < 50 | AI活用時の情報漏えい、著作権、誤情報への注意が必要です |
| データ活用力 < 50 | 効果測定や判断材料の整理に伸びしろがあります |
| 業務改善力 < 50 | ツール活用の前に、業務課題を整理する力を伸ばすとよいでしょう |
| 組織推進力 < 50 | 個人活用からチーム展開へ広げる準備が必要です |
| DX企画力 < 50 | 導入目的や費用対効果を考える力を伸ばすとよいでしょう |

## 14. 組織分析指標

| 指標 | 見ること |
| --- | --- |
| 平均総合スコア | 全体のAI・DX成熟度 |
| タイプ分布 | どんな人材が多いか |
| 能力別平均 | 組織の強み・弱み |
| 職種別スコア | 部署や職種ごとの差 |
| 役職別スコア | 管理職と一般社員の差 |
| リスク低スコア割合 | AI利用上の危険度 |
| Lv.4以上の割合 | 推進人材の候補数 |

## 15. JSON設計

`diagnosis_config.json` には以下を含める。

- app
- abilities
- answer_options
- levels
- types
- type_rules
- warnings
- radar_chart
- auth
- storage
- admin
- analytics_metrics
- questions

## 16. 結果表示前ログイン機能

診断結果は、以下の条件を満たすまで表示しない。

```text
全30問に回答済み
かつ
入力者情報が登録済み
かつ
個人情報・診断結果の保存に同意済み
かつ
診断結果の保存が成功済み
```

入力者情報フォームは、診断回答後、結果表示前に表示する。

| 項目 | 必須 | 種類 |
| --- | ---: | --- |
| 氏名 | 必須 | text |
| メールアドレス | 必須 | email |
| 会社名 | 任意 | text |
| 部署 | 任意 | text |
| 職種 | 任意 | text |
| 役職 | 任意 | text |

結果表示前に以下の同意チェックを表示する。

```text
入力した個人情報と診断結果が管理者に共有・保存されることに同意します
```

同意がない場合、結果表示と保存は実行しない。

## 17. セッション管理

Streamlitの `st.session_state` を使用して状態を管理する。

| キー | 内容 |
| --- | --- |
| answers | 各設問の回答 |
| is_answered | 全問回答済みかどうか |
| user_info | 入力者情報 |
| is_logged_in | 入力者情報登録済みかどうか |
| result_saved | スプレッドシート保存済みかどうか |

保存条件は以下とする。

```python
if is_answered and is_logged_in and not result_saved:
    save_result_to_spreadsheet()
    result_saved = True
```

再診断時は `answers`, `is_answered`, `user_info`, `is_logged_in`, `result_saved` を初期化する。

## 18. Googleスプレッドシート保存

初期実装では、保存先をGoogleスプレッドシートとする。

```text
スプレッドシート名: AI_DX_Diagnosis_Results
ワークシート名: diagnosis_results
```

既存のスプレッドシートに保存する場合は、`diagnosis_config.json` の `storage.spreadsheet_id` にスプレッドシートIDを指定できる。未指定の場合は、スプレッドシート名で検索し、見つからない場合は新規作成する。

保存タイミングは、入力者情報登録後、結果を表示する直前とする。

保存に失敗した場合は、以下のエラーを表示し、原則として結果は表示しない。

```text
診断結果の保存に失敗しました。時間をおいて再度お試しください。
```

Googleスプレッドシート連携に必要な認証情報はコードに直接書かず、Streamlit Secretsを使用する。

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

## 19. 保存データ項目

Googleスプレッドシートには、以下の項目を1診断につき1行で保存する。

| カラム名 | 内容 |
| --- | --- |
| diagnosis_id | 診断ID |
| created_at | 診断日時 |
| name | 氏名 |
| email | メールアドレス |
| company | 会社名 |
| department | 部署 |
| job_type | 職種 |
| position | 役職 |
| diagnosis_type | 診断タイプ |
| overall_score | 総合スコア |
| overall_level | 総合レベル |
| ai_basic_score | AI基礎理解スコア |
| tool_usage_score | ツール活用力スコア |
| business_issue_score | 業務課題発見力スコア |
| data_usage_score | データ活用力スコア |
| dx_planning_score | DX企画力スコア |
| risk_management_score | リスク管理能力スコア |
| organization_drive_score | 組織推進力スコア |
| answers_json | 各設問の回答データJSON |

## 20. 管理者確認

初期実装では、管理者はGoogleスプレッドシートを直接確認する。

管理者は以下を確認できる。

- 誰が診断を受けたか
- いつ診断を受けたか
- 診断タイプ
- 総合スコア
- 総合レベル
- 能力別スコア
- 部署別・職種別・役職別の傾向
- リスク管理能力が低い入力者
- Lv4以上の推進人材候補

## 21. JSON追加設定

ログイン風フォーム、保存、管理機能はJSONで有効・無効を切り替えられるようにする。

```json
{
  "auth": {
    "enabled": true,
    "required_before_result": true,
    "method": "profile_form",
    "fields": [],
    "consent": {
      "enabled": true,
      "required": true,
      "label": "入力した個人情報と診断結果が管理者に共有・保存されることに同意します"
    }
  },
  "storage": {
    "enabled": true,
    "type": "google_spreadsheet",
    "spreadsheet_id": "",
    "spreadsheet_name": "AI_DX_Diagnosis_Results",
    "worksheet_name": "diagnosis_results",
    "save_timing": "before_result_display"
  },
  "admin": {
    "enabled": true,
    "view_type": "spreadsheet",
    "metrics": []
  }
}
```

## 22. 将来的な拡張

- Googleログイン
- Microsoftログイン
- Supabase Auth
- 管理者専用ダッシュボード
- データベース保存
- 部署別レポート自動生成
- 回答者への診断結果メール送信

## 23. 完成条件

- StreamlitでWeb表示できる
- `diagnosis_config.json` を読み込める
- 30問すべて表示される
- 5択の回答を0〜4点で集計できる
- 能力別スコアを100点換算できる
- 総合スコアを7能力平均で算出できる
- 診断タイプを表示できる
- 総合レベルと能力別レベルを表示できる
- 7能力レーダーチャートを表示できる
- 注意コメントを表示できる
- おすすめアクションを表示できる
- 結果表示前に入力者情報フォームを表示できる
- 氏名・メールアドレス・同意チェックを必須にできる
- 保存成功前は診断結果を表示しない
- Googleスプレッドシートに診断結果を保存できる
- 同じセッションで重複保存しない
- CSV出力できる
- CSVまたは保存データをもとに組織分析できる
