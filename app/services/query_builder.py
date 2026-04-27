"""WHERE/SELECT clause builder shared by code_generator and azure_client."""
import re

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_VALID_OPS = {"=", "<=", "<", ">=", ">", "!="}


def _safe_id(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"無効なテーブル/カラム名: {name!r}")
    return name


def _expand_sql(sql: str, params) -> str:
    """Replace ? placeholders with actual values for display."""
    parts = sql.split('?')
    if len(parts) != len(params) + 1:
        return sql
    result = [parts[0]]
    for val, tail in zip(params, parts[1:]):
        if val is None:
            result.append('NULL')
        elif isinstance(val, str):
            result.append("'" + val.replace("'", "''") + "'")
        else:
            result.append(str(val))
        result.append(tail)
    return ''.join(result)


def build_select_clause(select_items, selectable_columns):
    if not select_items:
        select_items = [c for c in selectable_columns if c != "count"]

    parts = []
    for item in select_items:
        if item == "count":
            parts.append("COUNT(*)")
        elif item in selectable_columns:
            parts.append(_safe_id(item))
    return ", ".join(parts) if parts else "*"


def build_where_clause(filters, filterable_columns, columns_meta=None):
    """
    columns_meta: {col_name: {"allow_like": bool, "allow_array": bool,
                               "allow_operators": [str, ...]}}
    フィルタ値の形式:
      - 通常値          → col = ?
      - str with %/_    → col LIKE ?  (allow_like が True の場合)
      - list            → col IN (...)  (allow_array が True の場合)
      - {"op": X, "value": V} → col X ?  (X が allow_operators に含まれる場合)
    """
    where_parts = []
    params = []
    if not filters:
        return "", []

    meta_map = columns_meta or {}

    for col, val in filters.items():
        if col not in filterable_columns:
            continue
        safe_col = _safe_id(col)
        meta = meta_map.get(col, {})
        allow_like  = meta.get("allow_like",  True)
        allow_array = meta.get("allow_array", True)
        allowed_ops = set(meta.get("allow_operators", ["="]))

        if isinstance(val, list) and allow_array:
            placeholders = ",".join("?" * len(val))
            where_parts.append(f"{safe_col} IN ({placeholders})")
            params.extend(val)
        elif isinstance(val, dict) and "op" in val:
            op = val.get("op", "=")
            v  = val.get("value")
            if op in _VALID_OPS and op in allowed_ops:
                where_parts.append(f"{safe_col} {op} ?")
                params.append(v)
        elif isinstance(val, str) and allow_like and ("%" in val or "_" in val):
            where_parts.append(f"{safe_col} LIKE ?")
            params.append(val)
        elif "=" in allowed_ops:
            where_parts.append(f"{safe_col} = ?")
            params.append(val)

    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    return where_clause, params


def execute_query(db_path, target_table, select_items, filters, limit,
                  selectable_columns, filterable_columns, columns_meta=None,
                  query_type="rows"):
    import sqlite3

    where_clause, filter_params = build_where_clause(filters, filterable_columns, columns_meta)

    if query_type == "count":
        sql = f"SELECT COUNT(*) FROM {_safe_id(target_table)} {where_clause}".strip()
        exec_params = list(filter_params)
    else:
        select_clause = build_select_clause(select_items, selectable_columns)
        sql = f"SELECT DISTINCT {select_clause} FROM {_safe_id(target_table)} {where_clause} LIMIT ?".strip()
        exec_params = list(filter_params) + [limit]

    expanded_sql = _expand_sql(sql, exec_params)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, exec_params).fetchall()

    return expanded_sql, filter_params, [dict(r) for r in rows]
