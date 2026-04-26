from ..database import get_db


def get_all():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM tbl_tool_functions ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_by_id(function_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM tbl_tool_functions WHERE id = ?", (function_id,)
    ).fetchone()
    return dict(row) if row else None


def get_full(function_id):
    func = get_by_id(function_id)
    if not func:
        return None
    db = get_db()
    cols = db.execute(
        "SELECT * FROM tbl_tool_columns WHERE function_id = ? ORDER BY sort_order, id",
        (function_id,),
    ).fetchall()
    func["columns"] = [dict(c) for c in cols]
    return func


def create(data):
    db = get_db()
    cur = db.execute(
        """INSERT INTO tbl_tool_functions
           (name, target_table, description, usage_examples,
            filters_description, select_description, limit_default)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data["target_table"],
            data.get("description", ""),
            data.get("usage_examples", ""),
            data.get("filters_description", ""),
            data.get("select_description", ""),
            int(data.get("limit_default", 100)),
        ),
    )
    db.commit()
    return cur.lastrowid


def update(function_id, data):
    db = get_db()
    db.execute(
        """UPDATE tbl_tool_functions SET
           name=?, target_table=?, description=?, usage_examples=?,
           filters_description=?, select_description=?, limit_default=?,
           updated_at=datetime('now')
           WHERE id=?""",
        (
            data["name"],
            data["target_table"],
            data.get("description", ""),
            data.get("usage_examples", ""),
            data.get("filters_description", ""),
            data.get("select_description", ""),
            int(data.get("limit_default", 100)),
            function_id,
        ),
    )
    db.commit()


def delete(function_id):
    db = get_db()
    db.execute("DELETE FROM tbl_tool_functions WHERE id = ?", (function_id,))
    db.commit()
