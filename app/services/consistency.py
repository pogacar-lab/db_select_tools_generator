"""Consistency check between tool definitions and actual DB schema."""
from ..database import get_db, get_data_tables, get_table_columns
from ..models.tool_functions import get_all, get_full

# テーブル定義のカラム情報に、ツール定義にないカラムがあるかの除外リスト
_EXCLUDED_COLUMNS = {
    "id",
}


def check_function(function_id):
    func = get_full(function_id)
    if not func:
        return None

    issues = []
    db = get_db()

    exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (func["target_table"],),
    ).fetchone()

    if not exists:
        issues.append({"level": "CRITICAL", "message": f"対象テーブル '{func['target_table']}' がDBに存在しません"})
        return _build_report(func, issues)

    actual_cols = {c["name"] for c in get_table_columns(func["target_table"])}
    defined_cols = func.get("columns", [])
    defined_names = {c["column_name"] for c in defined_cols}

    for col in defined_cols:
        if col["column_name"] not in actual_cols:
            issues.append({
                "level": "ERROR",
                "message": f"カラム '{col['column_name']}' はツール定義にありますが実テーブルに存在しません",
            })

    for col_name in actual_cols:
        if col_name not in defined_names and col_name not in _EXCLUDED_COLUMNS:
            issues.append({
                "level": "WARNING",
                "message": f"実テーブルのカラム '{col_name}' がツール定義に未登録です",
            })

    selectable = [c for c in defined_cols if c["is_selectable"]]
    if not selectable:
        issues.append({"level": "ERROR", "message": "is_selectable=1 のカラムが1件もありません"})

    if not func.get("description", "").strip():
        issues.append({"level": "WARNING", "message": "関数のdescriptionが未設定です"})

    if not func.get("usage_examples", "").strip():
        issues.append({"level": "WARNING", "message": "使用例(usage_examples)が未設定です"})

    for col in defined_cols:
        if not col.get("select_items_description", "").strip():
            issues.append({
                "level": "WARNING",
                "message": f"カラム '{col['column_name']}' の select_items_description が未設定です",
            })

    return _build_report(func, issues)


def _build_report(func, issues):
    if any(i["level"] == "CRITICAL" for i in issues):
        status = "CRITICAL"
    elif any(i["level"] == "ERROR" for i in issues):
        status = "ERROR"
    elif any(i["level"] == "WARNING" for i in issues):
        status = "WARNING"
    else:
        status = "OK"

    return {
        "function_id": func["id"],
        "function_name": func["name"],
        "target_table": func["target_table"],
        "status": status,
        "issues": issues,
    }


def check_all():
    funcs = get_all()
    return [check_function(f["id"]) for f in funcs]
