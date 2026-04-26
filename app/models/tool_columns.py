from ..database import get_db


def get_for_function(function_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM tbl_tool_columns WHERE function_id = ? ORDER BY sort_order, id",
        (function_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def bulk_save(function_id, column_rows):
    db = get_db()
    db.execute("DELETE FROM tbl_tool_columns WHERE function_id = ?", (function_id,))
    for i, col in enumerate(column_rows):
        db.execute(
            """INSERT INTO tbl_tool_columns
               (function_id, column_name, select_items_description, filter_description,
                is_filterable, is_selectable,
                allow_like, allow_array, allow_operators, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                function_id,
                col["column_name"],
                col.get("select_items_description", ""),
                col.get("filter_description", ""),
                1 if col.get("is_filterable") else 0,
                1 if col.get("is_selectable") else 0,
                1 if col.get("allow_like", True) else 0,
                1 if col.get("allow_array", True) else 0,
                col.get("allow_operators", "="),
                i,
            ),
        )
    db.commit()
