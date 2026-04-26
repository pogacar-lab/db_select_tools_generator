# DB Select Tools Generator

SQLite3 DBファイルの定義をもとに、Azure OpenAI / OpenAI（GPT）向けの **function calling アクセス部品（参照専用。Pythonコード＋tools JSON）** を自動生成するFlask Webアプリです。

実際のデータと当ツール用情報（アクセス部品生成に利用する）を同一DBに保持する構成です。（つまり、このツール自体は対象DBファイルを更新する。ただし、テスト履歴は別DBに保存する）

---

## 主な機能

- **ツール定義管理** — 対象テーブル・カラムの和名・説明を Web UI で登録・編集
- **コード生成** — SELECT専用のPython関数と tools JSON を即時生成・ダウンロード
- **整合性チェック** — 実テーブルのスキーマとツール定義のズレを自動検出
- **APIテスト** — Azure OpenAI / OpenAI API を呼び出してtool callを試行。マルチターンのtool callループに対応。APIキーが未設定でも **Dry-Runモード** でSQL実行まで確認可能
- **テスト履歴** — 全実行結果（通常・ドライラン）を別DBに保存し、後から照会・メモ追記できる
- **APIログ出力** — テスト実行時のリクエスト／レスポンスを JSON ファイルに自動保存

---

## 動作環境

| 要件 | バージョン |
|------|-----------|
| Python | 3.11 以上 |
| Flask | 3.0 以上 |
| openai | 1.0 以上 |
| python-dotenv | 1.0 以上 |

---

## セットアップ

### 1. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルを作成

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # Mac/Linux
```

`.env` を編集して必要な値を設定します（次章参照）。

### 3. データディレクトリに対象DBを配置

`data/` ディレクトリに参照したい SQLite3 DB ファイルを配置し、`.env` の `DB_PATH` にパスを設定します。

---

## 設定（.env）

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `DB_PATH` | 参照する SQLite3 DB のパス | `./data/sample.db` |
| `HISTORY_DB_PATH` | テスト結果保存先 DB のパス | `./data/history.db` |
| `API_LOG_DIR` | APIリクエスト／レスポンスのログ出力先 | `./data/api_logs` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI のエンドポイント URL | — |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API キー。`DUMMY` → Dry-Runモード、`OPENAI` → OpenAIモード | `DUMMY` |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI モデルデプロイ名 | — |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API バージョン | `2025-01-01-preview` |
| `OPENAI_API_KEY` | OpenAI API キー（OpenAIモード時、ライブラリが環境変数から自動取得） | — |
| `OPENAI_MODEL` | OpenAI モデル名（OpenAIモード時） | — |
| `OPENAI_ENDPOINT` | OpenAI エンドポイント（省略時はデフォルト） | — |

### 動作モード

| `AZURE_OPENAI_API_KEY` の値 | 動作 |
|---|---|
| `DUMMY`（デフォルト） | **Dry-Runモード** — API呼び出しなし、SQL実行のみ |
| `OPENAI` | **OpenAIモード** — OpenAI API を使用 |
| それ以外 | **通常モード** — Azure OpenAI API を使用 |

---

## 起動

```bash
python run.py  --port 5000
```

ブラウザで `http://localhost:5000/` を開きます。

---

## 画面構成

| 画面名 | 機能 | テンプレート |
|--------|------|-------------|
| ツール関数一覧画面（`/`） | 登録済みツール関数の一覧。全関数まとめてPython/JSONのダウンロードが可能。 | `dashboard.html` |
| 関数作成・変更画面（`/tools/new` / `/tools/<id>/edit`） | 関数名・対象テーブル・説明・使用例・limitのデフォルト値を登録・編集。id なしで新規、id ありで変更。 | `editor/function_form.html` |
| テーブル定義照会画面（`/table/<table_name>`） | 実テーブルのカラム定義（型・NN・PK・AI・U・デフォルト・検査・外部キー）を表示。 | `table_info.html` |
| コード確認画面（`/output/<id>`） | 生成されたPythonコードとtools JSONの確認・コピー・ダウンロード。 | `output/view.html` |
| 整合性チェック画面（`/check/`） | ツール定義と実テーブルのスキーマのズレを自動検出しレポート表示。 | `consistency/report.html` |
| APIテスト画面（`/apitest/`） | Azure OpenAI / OpenAI APIでtool callを実行しSQL結果を表示。マルチターンループ・Dry-Runモード対応。 | `apitest/test.html` |
| テスト履歴画面（`/apitest/history`） | 全テスト結果の一覧・詳細表示。後からメモ追記・削除が可能。 | `apitest/history_list.html`<br>`apitest/history_detail.html` |

---

## 整合性チェックの判定基準

登録済みのツール定義と実テーブルのスキーマを比較し、問題をレポート表示します。
ステータスは最も深刻なレベルで決まります（CRITICAL > ERROR > WARNING > OK）。

| ステータス | チェック内容 |
|-----------|-------------|
| `CRITICAL` | 対象テーブルがDBに存在しない |
| `ERROR` | ツール定義に登録されたカラムが実テーブルに存在しない |
| `ERROR` | `is_selectable=1` のカラムが1件もない |
| `WARNING` | 実テーブルのカラムがツール定義に未登録 |
| `WARNING` | 関数の `description` が未設定 |
| `WARNING` | `usage_examples`（使用例）が未設定 |
| `WARNING` | いずれかのカラムの `select_items_description` が未設定 |
| `OK` | 上記の問題がすべてない |

---

## DBファイルの構造

対象DBファイルには、実データテーブルに加えて以下の**ツール定義テーブル**が同居します（自動作成）。

### `tbl_tool_functions` — 関数定義

| カラム | 型 | 説明 |
|--------|----|------|
| `id` | INTEGER PK | |
| `name` | TEXT UNIQUE | (LLMが呼び出す)関数名 |
| `target_table` | TEXT | 参照先テーブル名 |
| `description` | TEXT | LLMへの1行説明 |
| `usage_examples` | TEXT | 使用例（改行区切り） |
| `filters_description` | TEXT | filtersパラメタの説明 |
| `select_description` | TEXT | select_itemsパラメタの説明 |
| `limit_default` | INTEGER | limitのデフォルト値 |

### `tbl_tool_columns` — カラム定義

| カラム | 型 | 説明 |
|--------|----|------|
| `id` | INTEGER PK | |
| `function_id` | INTEGER FK | tbl_tool_functions.id |
| `column_name` | TEXT | 実カラム名 |
| `select_items_description` | TEXT | select_items用の説明（和名など） |
| `filter_description` | TEXT | filters用の説明 |
| `is_filterable` | INTEGER | 1=filtersで使用可 |
| `is_selectable` | INTEGER | 1=select_itemsで使用可 |
| `allow_like` | INTEGER | 1=LIKE検索を許可 |
| `allow_array` | INTEGER | 1=IN句（配列）を許可 |
| `allow_operators` | TEXT | 許可する比較演算子（カンマ区切り、例: `=,>=,<=`） |
| `sort_order` | INTEGER | 表示順 |

---

## 生成されるtools JSON の仕様

OpenAI function calling 形式（Azure OpenAI / OpenAI 共通）で生成されます。パラメタの順序は `query_type` → `select_items` → `filters` → `limit` です。

```json
{
  "type": "function",
  "function": {
    "name": "get_programs",
    "description": "プログラム一覧を取得します。\n\n使用例:\n- カテゴリを指定して件数を取得する",
    "parameters": {
      "type": "object",
      "properties": {
        "query_type": {
          "type": "string",
          "enum": ["rows", "count"],
          "description": "rows: プログラム一覧を取得します。count: 条件に合う件数のみを取得する。countの場合、select_itemsは使用しない。"
        },
        "select_items": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["program_name", "category", "lines"]
          },
          "description": "query_typeがrowsの場合のみ指定する。回答に必要な列だけを指定する。query_typeがcountの場合は指定しない。"
        },
        "filters": {
          "type": "object",
          "description": "絞り込み条件。%/_を含む文字列はLIKE、配列はIN句、複数項目はANDで結合。",
          "properties": {
            "category": {
              "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}}
              ],
              "description": "カテゴリ: プログラムの分類"
            }
          }
        },
        "limit": {
          "type": "integer",
          "description": "最大取得件数。query_typeがcountの場合は無視する。",
          "default": 100
        }
      },
      "required": ["query_type", "filters"]
    }
  }
}
```

---

## 生成されるPythonコードの仕様

生成された関数の引数は `query_type` → `select_items` → `filters` → `limit` の順です。

```python
def get_programs(
    query_type: str = "rows",
    select_items: Optional[list] = None,
    filters: Optional[dict] = None,
    limit: int = 100,
) -> list[dict]:
```

### query_type の動作

| `query_type` | SQL展開 |
|---|---|
| `"rows"` | `SELECT <select_items> FROM table WHERE ... LIMIT ?` |
| `"count"` | `SELECT COUNT(*) FROM table WHERE ...`（LIMIT なし） |

### filters の展開ルール

| filtersの値 | SQL展開 |
|------------|---------|
| `{"name": "Python"}` | `WHERE name = ?` |
| `{"name": "%Python%"}` | `WHERE name LIKE ?`（`%` または `_` を含む場合） |
| `{"id": [1, 2, 3]}` | `WHERE id IN (?, ?, ?)` |
| `{"lines": {"op": ">=", "value": 100}}` | `WHERE lines >= ?` |
| 複数キー指定 | `WHERE ... AND ...` |

### select_items の展開ルール（query_type=rows の場合）

| select_itemsの値 | SQL展開 |
|-----------------|---------|
| 省略 / 空リスト | 全取得可カラムを `SELECT` |
| `["name", "category"]` | `SELECT name, category` |

---

## APIログ出力

テスト実行のたびに `API_LOG_DIR`（デフォルト: `./data/api_logs/`）へ JSON ファイルを自動出力します。

| ファイル名 | 内容 | 出力条件 |
|---|---|---|
| `YYYYMMDD_HHMMSS_<id>_request.json` | エンドポイント・モデル・メッセージ・tools（APIキーは `***`） | 常時 |
| `YYYYMMDD_HHMMSS_<id>_response.json` | LLM からの生レスポンス | 通常モードのみ |

---

## ディレクトリ構成

```
DBアクセス部品/
├── .env                        # 設定ファイル（要作成）
├── .env.example                # 設定ファイルのテンプレート
├── .gitignore
├── requirements.txt
├── run.py                      # 起動エントリポイント
│
├── data/
│   ├── sample.db               # 対象DBファイル（任意のSQLite3 DB）
│   ├── history.db              # テスト結果保存DB（自動作成）
│   └── api_logs/               # APIリクエスト／レスポンスログ（自動作成）
│
└── app/
    ├── __init__.py             # Flaskアプリファクトリ
    ├── config.py               # .env 読み込み
    ├── database.py             # DB接続・スキーマ初期化
    ├── models/
    │   ├── tool_functions.py   # tbl_tool_functions CRUD
    │   └── tool_columns.py     # tbl_tool_columns CRUD
    ├── services/
    │   ├── query_builder.py    # WHERE/SELECT句組み立て（生成・実行共通）
    │   ├── json_generator.py   # tools JSON生成
    │   ├── code_generator.py   # Python関数コード生成
    │   ├── consistency.py      # スキーマ整合性チェック
    │   ├── azure_client.py     # Azure OpenAI / OpenAI API呼び出し
    │   └── history.py          # テスト結果の保存・照会
    ├── routes/
    │   ├── dashboard.py        # /
    │   ├── editor.py           # /tools/*
    │   ├── output.py           # /output/*
    │   ├── consistency.py      # /check/*
    │   └── apitest.py          # /apitest/*
    └── templates/
        ├── base.html
        ├── dashboard.html
        ├── table_info.html
        ├── editor/
        │   └── function_form.html
        ├── output/view.html
        ├── consistency/report.html
        └── apitest/
            ├── test.html
            ├── history_list.html
            └── history_detail.html
```
