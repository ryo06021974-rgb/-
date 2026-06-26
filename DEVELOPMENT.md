# 開発仕様書

共同開発者向けの技術仕様書です。アーキテクチャ・データ定義・コーディングルール・拡張方法を記載します。

---

## 目次

1. [アーキテクチャ](#1-アーキテクチャ)
2. [ファイル責務](#2-ファイル責務)
3. [diagnosis_config.json スキーマ](#3-diagnosis_configjson-スキーマ)
4. [診断フロー](#4-診断フロー)
5. [セッション状態](#5-セッション状態)
6. [スコア計算ロジック](#6-スコア計算ロジック)
7. [タイプ判定ロジック](#7-タイプ判定ロジック)
8. [保存ロジック](#8-保存ロジック)
9. [コーディング規約](#9-コーディング規約)
10. [機能拡張ガイド](#10-機能拡張ガイド)
11. [設定の有効化・無効化](#11-設定の有効化無効化)
12. [ローカル開発手順](#12-ローカル開発手順)

---

## 1. アーキテクチャ

**原則: ロジックとデータの完全分離**

```
app.py                   ← ロジック・表示のみ。診断内容はここに書かない
diagnosis_config.json    ← すべての診断データ（設問・タイプ・レベル・ルール等）
.streamlit/secrets.toml  ← 認証情報（Git管理外）
results.csv              ← 診断結果の蓄積（実行時生成）
```

- 設問・タイプ・レベル・注意コメントの追加・変更は `diagnosis_config.json` のみを編集する
- `app.py` はJSONを読み込んで汎用的に動作する。特定の設問IDや能力IDをハードコードしない
- 機能の有効・無効は `auth.enabled` / `storage.enabled` のフラグで制御する

---

## 2. ファイル責務

### app.py 関数一覧

| 関数 | 役割 |
| --- | --- |
| `load_config()` | JSONを読み込んで返す |
| `validate_config(config)` | 設定の整合性チェック（起動時に必ず実行） |
| `ordered_abilities(config)` | `order` キーでソートした能力リストを返す |
| `initialize_session_state()` | セッション変数を初期値で初期化 |
| `calculate_scores(config, answers)` | 回答から能力別スコア・総合スコアを計算 |
| `determine_types(config, overall_score, ability_scores)` | タイプを判定して返す |
| `collect_warnings(config, ability_scores)` | 注意コメントを収集 |
| `build_radar_chart(config, ability_scores)` | Plotlyレーダーチャートを生成 |
| `build_result(config, answers, profile)` | 診断結果オブジェクトを構築 |
| `build_result_record(config, result)` | 保存用のフラットな辞書を生成 |
| `save_result_to_storage(config, result)` | ストレージに保存（現在はスプレッドシートのみ） |
| `render_question_form(config)` | 設問フォームを表示 |
| `render_auth_form(config)` | 入力者情報フォームを表示 |
| `render_result(config, result)` | 診断結果を表示 |
| `render_analytics(config)` | 組織分析を表示 |
| `reset_diagnosis()` | 再診断のためにセッションをリセット |

---

## 3. diagnosis_config.json スキーマ

### 3-1. app

```json
"app": {
  "title": "string",           // アプリのタイトル
  "description": "string",     // アプリの説明文
  "question_count": 30,        // 設問数（questions配列の長さと一致させる）
  "score_min": 0,              // 回答選択肢の最低点
  "score_max": 4,              // 回答選択肢の最高点
  "results_file": "string",    // CSV保存先のファイル名
  "shuffle_questions": false   // trueにすると設問をランダム順で表示
}
```

### 3-2. abilities

診断の7能力を定義する配列。

```json
{
  "id": "string",        // 一意のスネークケースID（例: ai_basic）
  "name": "string",      // 表示名
  "description": "string",
  "order": 1             // 表示順（数値が小さいほど先）
}
```

**現在の能力ID一覧（変更時は全参照箇所を確認）:**  
`ai_basic` / `tool_usage` / `business_issue` / `data_usage` / `dx_planning` / `risk_management` / `organization_drive`

### 3-3. answer_options

回答選択肢の配列。フォームでの表示順がそのまま使われる。

```json
{
  "id": "string",    // 一意のID（例: cannot）
  "label": "string", // 表示ラベル
  "score": 0         // 整数。score_min〜score_max の範囲内
}
```

### 3-4. levels

スコアに対するレベルの閾値を定義する配列。`min_score` の昇順で定義する。

```json
{
  "id": "string",
  "label": "string",       // 例: "Lv1"
  "name": "string",        // 例: "入門者"
  "min_score": 0,          // このレベルの下限スコア（以上）
  "max_score": 39,         // このレベルの上限スコア（以下）
  "description": "string",
  "next_action": "string"  // おすすめアクションに表示するテキスト
}
```

レベル判定は `min_score` の昇順で評価し、条件を満たす最後のレベルを採用する。

### 3-5. types

診断タイプの定義。

```json
{
  "id": "string",
  "name": "string",
  "summary": "string",
  "recommended_actions": ["string", ...]
}
```

### 3-6. type_rules

タイプ判定ルール。`priority` が小さいほど先に評価される。

**overall_range タイプ（総合スコア範囲で決まる）:**

```json
{
  "id": "string",
  "rule_type": "overall_range",
  "type_id": "string",   // types.id を参照
  "min_score": 0,
  "max_score": 39,
  "priority": 1          // 数値が小さいほど優先
}
```

**top_ability タイプ（最高スコアの能力で決まる）:**

```json
{
  "id": "string",
  "rule_type": "top_ability",
  "ability_id": "string", // abilities.id を参照
  "type_id": "string",
  "priority": 10
}
```

判定順序:
1. `overall_range` ルールを `priority` 順に評価し、最初にマッチしたタイプを返す
2. マッチしなければ最高スコアの能力に対応する `top_ability` ルールを適用
3. 同スコアの能力が複数あれば複合タイプとして返す

### 3-7. warnings

能力スコアが閾値を下回った場合に表示する注意コメント。

```json
{
  "id": "string",
  "ability_id": "string",  // abilities.id を参照
  "threshold": 50,         // この値未満のとき警告を表示
  "message": "string"
}
```

### 3-8. radar_chart

```json
"radar_chart": {
  "title": "string",
  "min": 0,
  "max": 100,
  "ability_ids": ["string", ...]  // レーダーチャートに表示する能力IDの順序
}
```

### 3-9. auth

入力者情報フォームの設定。

```json
"auth": {
  "enabled": true,                  // フォーム全体の有効化
  "required_before_result": true,   // trueなら結果表示前に強制表示
  "method": "profile_form",
  "fields": [
    {
      "id": "string",     // セッションのキーになる（例: name, email）
      "label": "string",  // フォームラベル
      "type": "text",     // "text" or "email"（emailはバリデーション付き）
      "required": true
    }
  ],
  "consent": {
    "enabled": true,    // 同意チェックボックスの表示
    "required": true,   // trueなら同意なしで進めない
    "label": "string"
  }
}
```

`required_before_result: false` の場合、フォームはスキップされプロフィールは空になる。

### 3-10. storage

```json
"storage": {
  "enabled": true,
  "type": "google_spreadsheet",   // 現在はこの値のみ有効
  "spreadsheet_id": "string",     // 空文字の場合はspreadsheet_nameで検索
  "spreadsheet_name": "string",
  "worksheet_name": "string",
  "save_timing": "before_result_display"  // 現在はこの値のみ
}
```

`spreadsheet_id` が指定されている場合はIDで直接開く（推奨）。未指定の場合はスプレッドシート名で検索するが、見つからなければエラーになる（自動作成しない）。

### 3-11. analytics_metrics

組織分析で表示する指標の定義。

| calculation | 説明 | 必須フィールド |
| --- | --- | --- |
| `count` | 行数をカウント | — |
| `mean` | 指定列の平均 | `column` |
| `value_counts` | 値ごとの件数 | `column` |
| `ability_means` | 全能力の平均スコア | — |
| `group_mean` | グループ別の平均 | `group_by`, `column` |
| `below_rate` | 閾値未満の割合 | `column`, `threshold` |
| `level_min_rate` | 指定レベル以上の割合 | `level_order_min` |

### 3-12. questions

設問の定義。`question_count` と配列の長さが一致している必要がある。

```json
{
  "id": "string",          // 一意のID（例: Q01, Q02...）
  "text": "string",        // 設問文
  "ability_id": "string",  // abilities.id を参照
  "category": "string",    // カテゴリ（現在は表示に使用しない）
  "sub_category": "string",
  "score_type": "0_to_4"   // 現在は "0_to_4" のみ
}
```

---

## 4. 診断フロー

```
[設問フォーム表示]
    ↓ 全問回答・送信
[回答をsession_stateに保存]
    ↓
[auth.required_before_result が true?]
  Yes → [入力者情報フォーム表示]
           ↓ 必須項目・同意チェック
        [user_infoをsession_stateに保存]
  No  → スキップ（user_info = {}）
    ↓
[storage.save_timing が "before_result_display" かつ未保存?]
  Yes → [Googleスプレッドシートに保存]
           → 失敗した場合は結果を表示せずエラー画面
  No  → スキップ
    ↓
[診断結果を表示]
    ↓
[再診断ボタン → session_stateをリセット → 先頭に戻る]
```

---

## 5. セッション状態

| キー | 型 | 説明 |
| --- | --- | --- |
| `answers` | `dict[str, str]` | `{question_id: option_id}` |
| `is_answered` | `bool` | 全問回答済みか |
| `user_info` | `dict` | 入力者情報（authが無効な場合は空） |
| `is_logged_in` | `bool` | 入力者情報登録済みか |
| `result_saved` | `bool` | スプレッドシートへの保存済みか |
| `result` | `dict` | `build_result()` の返り値（計算済み結果） |
| `question_order` | `list[str]` | 表示順の設問IDリスト（シャッフル対応） |

**重複保存の防止:** `result_saved` が `True` の間は `save_result_to_storage()` を呼ばない。再診断時はリセットされる。

---

## 6. スコア計算ロジック

```python
# 能力別スコア（0〜100点換算）
ability_score[ability_id] = (能力別得点合計 / 能力別満点) * 100

# 能力別満点 = その能力に紐づく設問数 × answer_optionsの最高点
# 総合スコア = 全能力スコアの平均
overall_score = sum(ability_scores.values()) / len(ability_scores)
```

**設問数の能力間バランスに注意:** 各能力に割り振る設問数が異なっても、100点換算するため能力間の不公平は生じない。

---

## 7. タイプ判定ロジック

```python
# Step 1: overall_range ルールを priority 昇順で評価
for rule in sorted(overall_range_rules, key=priority):
    if rule.min_score <= overall_score <= rule.max_score:
        return [type_by_id[rule.type_id]]

# Step 2: 最高スコアの能力を特定（同点は複数）
top_score = max(ability_scores.values())
top_ability_ids = {id for id, score in ability_scores.items() if score ≈ top_score}

# Step 3: top_ability ルールを priority 昇順で評価
for rule in sorted(top_ability_rules, key=priority):
    if rule.ability_id in top_ability_ids:
        selected_types.append(rule.type_id)  # 重複除去

# 結果が空の場合は types[0] を返す（フォールバック）
```

---

## 8. 保存ロジック

### 保存データ（スプレッドシート1行の構造）

| カラム | 内容 |
| --- | --- |
| `diagnosis_id` | UUID v4 |
| `created_at` | ISO 8601形式（秒精度） |
| `name` / `email` / `company` / `department` / `job_type` / `position` | 入力者情報 |
| `diagnosis_type` | タイプ名（複数は ` / ` 区切り） |
| `overall_score` | 総合スコア |
| `overall_level` | `Lv1 入門者` のような文字列 |
| `{ability_id}_score` | 能力別スコア（ordered_abilitiesの順） |
| `answers_json` | 全設問の回答詳細（JSON文字列） |

### ヘッダー管理

既存ワークシートのヘッダーと新しいレコードのキーが一致しない場合（新カラム追加時など）、`ensure_worksheet_header()` が不足カラムをヘッダー行に追記する。既存データは変更しない。

### 認証情報

`st.secrets` から `gcp_service_account` または `google_service_account` のいずれかのキーで取得する（両方ある場合は `gcp_service_account` が優先）。

---

## 9. コーディング規約

- **Python 3.x**（型ヒントは任意、追加してもよい）
- インデント: スペース4つ
- 変数・関数名: `snake_case`
- 定数: `UPPER_SNAKE_CASE`（例: `CONFIG_PATH`）
- JSONの能力IDなどの文字列をapp.pyにハードコードしない
- `app.py` に診断ロジックの定数（閾値・タイプ名等）を直接書かない
- Streamlitのウィジェットキーは `answer_{question_id}` / `auth_{field_id}` の命名規則に従う
- セッション状態のキーは`initialize_session_state()`で一元管理する

---

## 10. 機能拡張ガイド

### 設問を追加・変更する

1. `diagnosis_config.json` の `questions` 配列を編集
2. `app.question_count` を実際の設問数に合わせる
3. 新しい能力IDを使う場合は `abilities` にも追加する

### タイプを追加する

1. `types` に新しいタイプを追加
2. `type_rules` に判定ルールを追加（`priority` の値で評価順を制御）

### 入力者情報フォームの項目を追加する

1. `auth.fields` に項目を追加（`id` がそのまま保存カラム名のベースになる）
2. 新しい `id` を `build_result_record()` が自動的に拾うか確認する
   - `build_result_record()` は `user_info.get(field_id, "")` で値を取得するため、`auth.fields` の `id` と保存カラム名が対応している必要がある

### 組織分析の指標を追加する

1. `analytics_metrics` に新しい指標を追加
2. `calculation` が既存の種類で対応できない場合は `render_analytics()` に新しい分岐を追加する

### 新しい保存先（storage.type）を追加する

1. `save_result_to_storage()` に新しい `if` 分岐を追加
2. `validate_config()` の storage 検証を更新する

---

## 11. 設定の有効化・無効化

| 設定 | 有効化方法 | 無効化方法 |
| --- | --- | --- |
| 入力者情報フォーム | `auth.enabled: true` + `auth.required_before_result: true` | `auth.enabled: false` |
| 同意チェック | `auth.consent.enabled: true` | `auth.consent.enabled: false` |
| スプレッドシート保存 | `storage.enabled: true` | `storage.enabled: false` |
| 設問シャッフル | `app.shuffle_questions: true` | `app.shuffle_questions: false` |

**注意:** `auth.enabled: true` かつ `auth.required_before_result: false` の場合、フォームは表示されず `user_info` は空になる。

---

## 12. ローカル開発手順

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# アプリを起動
streamlit run app.py
```

### Googleスプレッドシート連携をローカルでテストする

1. `.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピー
2. GCPサービスアカウントの認証情報を設定
3. `diagnosis_config.json` の `storage.spreadsheet_id` に対象スプレッドシートのIDを設定
4. サービスアカウントに対象スプレッドシートの編集権限を付与

### スプレッドシートなしで動かす

```json
"storage": { "enabled": false }
```

または `auth.required_before_result: false` にすれば入力フォームもスキップできる。

### validate_config() でチェックされる内容

- `questions` の件数が `app.question_count` と一致する
- 設問IDに重複がない
- 設問の `ability_id` が `abilities` に存在する
- `answer_options` のスコアが `score_min`〜`score_max` の範囲内
- `type_rules` の `type_id` / `ability_id` が各定義に存在する
- `warnings` の `ability_id` が存在する
- `radar_chart.ability_ids` が全て存在する
- `auth.fields` のIDに重複がない
- `storage.type` が `google_spreadsheet` である（有効時）
- `storage.spreadsheet_name` / `worksheet_name` が空でない（有効時）

起動時にエラーが出た場合は上記の整合性を確認する。
