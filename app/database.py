import re
import sqlite3
from flask import g, current_app

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"無効なテーブル/カラム名: {name!r}")
    return name


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DB_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS tbl_tool_functions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL UNIQUE,
            target_table        TEXT NOT NULL,
            description         TEXT NOT NULL DEFAULT '',
            usage_examples      TEXT NOT NULL DEFAULT '',
            filters_description TEXT NOT NULL DEFAULT '',
            select_description  TEXT NOT NULL DEFAULT '',
            limit_default       INTEGER NOT NULL DEFAULT 100,
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tbl_tool_columns (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            function_id      INTEGER NOT NULL REFERENCES tbl_tool_functions(id) ON DELETE CASCADE,
            column_name               TEXT NOT NULL,
            select_items_description  TEXT NOT NULL DEFAULT '',
            filter_description        TEXT NOT NULL DEFAULT '',
            is_filterable    INTEGER NOT NULL DEFAULT 0,
            is_selectable    INTEGER NOT NULL DEFAULT 0,
            allow_like       INTEGER NOT NULL DEFAULT 1,
            allow_array      INTEGER NOT NULL DEFAULT 1,
            allow_operators  TEXT NOT NULL DEFAULT '=',
            sort_order       INTEGER NOT NULL DEFAULT 0,
            UNIQUE(function_id, column_name)
        );
    """)
    # 既存DBに新カラムを追加（マイグレーション）
    for col_def in [
        ("allow_like",      "INTEGER NOT NULL DEFAULT 1"),
        ("allow_array",     "INTEGER NOT NULL DEFAULT 1"),
        ("allow_operators", "TEXT NOT NULL DEFAULT '='"),
    ]:
        try:
            db.execute(f"ALTER TABLE tbl_tool_columns ADD COLUMN {col_def[0]} {col_def[1]}")
        except Exception:
            pass  # already exists
    # カラム名変更マイグレーション
    for old, new in [
        ("japanese_name", "select_items_description"),
        ("description",   "filter_description"),
    ]:
        try:
            db.execute(f"ALTER TABLE tbl_tool_columns RENAME COLUMN {old} TO {new}")
        except Exception:
            pass  # already renamed
    db.commit()


def get_table_schema(table_name: str) -> list:
    """テーブルの詳細スキーマ情報を返す（カラム・FK・UNIQUE・AI・CHECK含む）。"""
    _validate_identifier(table_name)
    db = get_db()

    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone():
        raise ValueError(f"テーブル '{table_name}' が存在しません")

    columns = [dict(r) for r in db.execute(f"PRAGMA table_info({table_name})").fetchall()]

    fk_map = {
        r["from"]: {"ref_table": r["table"], "ref_col": r["to"]}
        for r in db.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    }

    unique_cols = set()
    for idx in db.execute(f"PRAGMA index_list({table_name})").fetchall():
        if idx["unique"] and idx["origin"] == "u":
            for ic in db.execute(f"PRAGMA index_info({idx['name']})").fetchall():
                unique_cols.add(ic["name"])

    sql_row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    create_sql = sql_row["sql"] if sql_row else ""

    def _find_closing_paren(s, start):
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "(":
                depth += 1
            elif s[i] == ")":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _col_line(col_name):
        for line in create_sql.splitlines():
            s = line.strip().rstrip(",")
            if re.match(rf'^["`\[]?{re.escape(col_name)}["`\]]?\s', s, re.IGNORECASE):
                return s
        return ""

    def _is_autoincrement(col_name):
        return bool(re.search(r"\bAUTOINCREMENT\b", _col_line(col_name), re.IGNORECASE))

    def _check_constraint(col_name):
        line = _col_line(col_name)
        m = re.search(r"CHECK\s*\(", line, re.IGNORECASE)
        if not m:
            return ""
        end = _find_closing_paren(line, m.end() - 1)
        return f"CHECK({line[m.end():end]})" if end != -1 else ""

    return [
        {
            "name":      col["name"],
            "type":      col["type"],
            "notnull":   bool(col["notnull"]),
            "pk":        col["pk"],
            "is_ai":     _is_autoincrement(col["name"]),
            "is_unique": col["name"] in unique_cols,
            "default":   col["dflt_value"],
            "check":     _check_constraint(col["name"]),
            "fk":        fk_map.get(col["name"]),
        }
        for col in columns
    ]

# 除外テーブル一覧
_EXCLUDED_TABLES = {
    "tbl_tool_functions",
    "tbl_tool_columns",
    "sqlite_sequence",
}


def get_data_tables():
    db = get_db()
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows if r["name"] not in _EXCLUDED_TABLES]


def get_table_columns(table_name):
    _validate_identifier(table_name)
    db = get_db()
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [dict(r) for r in rows]


def get_history_db():
    if "history_db" not in g:
        g.history_db = sqlite3.connect(
            current_app.config["HISTORY_DB_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.history_db.row_factory = sqlite3.Row
    return g.history_db


def close_history_db(e=None):
    db = g.pop("history_db", None)
    if db is not None:
        db.close()


def init_history_db():
    db = get_history_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS tbl_test_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            executed_at     TEXT NOT NULL DEFAULT (datetime('now')),
            mode            TEXT NOT NULL,
            prompt          TEXT NOT NULL DEFAULT '',
            function_name   TEXT NOT NULL DEFAULT '',
            tools_json      TEXT NOT NULL DEFAULT '',
            tool_arguments  TEXT NOT NULL DEFAULT '',
            executed_sql    TEXT NOT NULL DEFAULT '',
            sql_params      TEXT NOT NULL DEFAULT '',
            result_count    INTEGER,
            results_json    TEXT NOT NULL DEFAULT '',
            raw_response    TEXT NOT NULL DEFAULT '',
            memo            TEXT NOT NULL DEFAULT ''
        );
    """)
    db.commit()
