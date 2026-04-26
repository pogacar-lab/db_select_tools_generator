from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..models import tool_functions, tool_columns
from ..database import get_data_tables, get_table_columns

bp = Blueprint("editor", __name__)


@bp.route("/table-columns")
def table_columns_api():
    """テーブルのカラム一覧をJSONで返す（新規関数作成フォームのAJAX用）。"""
    table = request.args.get("table", "")
    try:
        cols = get_table_columns(table)
        return jsonify([{"name": c["name"], "type": c["type"]} for c in cols])
    except ValueError:
        return jsonify([])


_ALL_OPERATORS = ["=", "<=", "<", ">=", ">", "!="]


def _extract_column_rows(form):
    rows = []
    col_names               = form.getlist("column_name")
    select_items_descs      = form.getlist("select_items_description")
    filter_descs            = form.getlist("filter_description")
    for i, col_name in enumerate(col_names):
        if not col_name.strip():
            continue
        jp   = select_items_descs[i].strip() if i < len(select_items_descs) else ""
        desc = filter_descs[i].strip()        if i < len(filter_descs)       else ""
        is_sel  = f"selectable_{i}"  in form
        is_filt = f"filterable_{i}"  in form
        if not is_sel and not is_filt:
            continue
        # フィルタ詳細オプション
        ops = [op for op in _ALL_OPERATORS if f"op_{_op_key(op)}_{i}" in form]
        rows.append({
            "column_name":             col_name.strip(),
            "select_items_description": jp,
            "filter_description":       desc,
            "is_selectable":  1 if is_sel  else 0,
            "is_filterable":  1 if is_filt else 0,
            "allow_like":     1 if f"allow_like_{i}"  in form else 0,
            "allow_array":    1 if f"allow_array_{i}" in form else 0,
            "allow_operators": ",".join(ops) if ops else "=",
        })
    return rows


def _op_key(op):
    return op.replace("=", "eq").replace("<", "lt").replace(">", "gt").replace("!", "ne")


@bp.route("/new", methods=["GET", "POST"])
@bp.route("/<int:function_id>/edit", methods=["GET", "POST"])
def edit_function(function_id=None):
    func = tool_functions.get_by_id(function_id) if function_id else None
    if function_id and not func:
        flash("関数が見つかりません", "danger")
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        data = request.form.to_dict()
        try:
            if func:
                tool_functions.update(function_id, data)
                col_rows = _extract_column_rows(request.form)
                tool_columns.bulk_save(function_id, col_rows)
                flash("更新しました", "success")
                return redirect(url_for("editor.edit_function", function_id=function_id))
            else:
                fid = tool_functions.create(data)
                col_rows = _extract_column_rows(request.form)
                if col_rows:
                    tool_columns.bulk_save(fid, col_rows)
                flash("関数を作成しました", "success")
                return redirect(url_for("output.view", function_id=fid))
        except Exception as e:
            flash(f"エラー: {e}", "danger")

    tables = get_data_tables()
    columns = None
    if func:
        existing = {c["column_name"]: c for c in tool_columns.get_for_function(function_id)}
        actual_cols = get_table_columns(func["target_table"]) if func["target_table"] else []
        columns = []
        for ac in actual_cols:
            col_name = ac["name"]
            saved = existing.get(col_name, {})
            columns.append({
                "column_name":     col_name,
                "select_items_description": saved.get("select_items_description", ""),
                "filter_description":       saved.get("filter_description",       ""),
                "is_filterable":   saved.get("is_filterable",  0) if saved else 0,
                "is_selectable":   saved.get("is_selectable",  0) if saved else 0,
                "allow_like":      saved.get("allow_like",     0) if saved else 0,
                "allow_array":     saved.get("allow_array",    0) if saved else 0,
                "allow_operators": saved.get("allow_operators", "=") if saved else "=",
                "db_type":         ac.get("type", ""),
            })
    return render_template("editor/function_form.html", func=func, tables=tables, columns=columns)


@bp.route("/<int:function_id>/delete", methods=["POST"])
def delete_function(function_id):
    tool_functions.delete(function_id)
    flash("削除しました", "success")
    return redirect(url_for("dashboard.index"))
