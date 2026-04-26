"""Test result history operations on history.db."""
import json
from ..database import get_history_db


def _expand_sql(sql, params):
    """Replace ? with actual values for display (best-effort for old records)."""
    if '?' not in sql or not params:
        return sql
    parts = sql.split('?')
    result = [parts[0]]
    for i, tail in enumerate(parts[1:]):
        if i < len(params):
            val = params[i]
            if val is None:
                result.append('NULL')
            elif isinstance(val, str):
                result.append("'" + val.replace("'", "''") + "'")
            else:
                result.append(str(val))
        else:
            result.append('?')
        result.append(tail)
    return ''.join(result)


def save(result):
    db = get_history_db()
    cur = db.execute(
        """INSERT INTO tbl_test_results
           (mode, prompt, function_name, tools_json, tool_arguments,
            executed_sql, sql_params, result_count, results_json, raw_response)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            result.get("mode", ""),
            result.get("prompt", ""),
            result.get("function_name", ""),
            result.get("tools_json", ""),
            json.dumps(result.get("tool_arguments", {}), ensure_ascii=False),
            result.get("executed_sql", ""),
            json.dumps(result.get("sql_params", []), ensure_ascii=False),
            result.get("result_count", 0),
            json.dumps(result.get("results", []), ensure_ascii=False),
            json.dumps(result.get("raw_response", {}), ensure_ascii=False),
        ),
    )
    db.commit()
    return cur.lastrowid


def get_list(page=1, per_page=20):
    db = get_history_db()
    offset = (page - 1) * per_page
    rows = db.execute(
        """SELECT id, executed_at, mode, function_name,
                  substr(prompt, 1, 60) as prompt_head, result_count, memo
           FROM tbl_test_results ORDER BY id DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM tbl_test_results").fetchone()[0]
    return [dict(r) for r in rows], total


def get_by_id(history_id):
    db = get_history_db()
    row = db.execute(
        "SELECT * FROM tbl_test_results WHERE id = ?", (history_id,)
    ).fetchone()
    if not row:
        return None
    r = dict(row)
    for field in ("tool_arguments", "sql_params", "results_json", "raw_response"):
        try:
            r[field] = json.loads(r[field]) if r[field] else ({} if field in ("tool_arguments", "raw_response") else [])
        except Exception:
            pass
    if '?' in (r.get('executed_sql') or ''):
        r['executed_sql'] = _expand_sql(r['executed_sql'], r.get('sql_params') or [])
    return r


def update_memo(history_id, memo):
    db = get_history_db()
    db.execute("UPDATE tbl_test_results SET memo=? WHERE id=?", (memo, history_id))
    db.commit()


def delete(history_id):
    db = get_history_db()
    db.execute("DELETE FROM tbl_test_results WHERE id=?", (history_id,))
    db.commit()
