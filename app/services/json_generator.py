"""Generate Azure OpenAI function calling tools JSON from tool definitions."""
import json


def _build_filter_property(col):
    allow_like  = bool(col.get("allow_like",  1))
    allow_array = bool(col.get("allow_array", 1))
    ops_str     = col.get("allow_operators", "=") or "="
    allowed_ops = [op.strip() for op in ops_str.split(",") if op.strip()]
    non_eq_ops  = [op for op in allowed_ops if op != "="]

    one_of = [{"type": "string"}]
    if allow_array:
        one_of.append({"type": "array", "items": {"type": "string"}})
    if non_eq_ops:
        one_of.append({
            "type": "object",
            "properties": {
                "op":    {"type": "string", "enum": non_eq_ops},
                "value": {"type": "string"},
            },
            "required": ["op", "value"],
        })

    desc = col.get("filter_description", "")
    extras = []
    if allow_like:
        extras.append("% や _ を含む文字列はLIKE検索")
    if allow_array:
        extras.append("配列はIN句")
    if non_eq_ops:
        ops_list = ", ".join(non_eq_ops)
        extras.append(f'演算子指定は {{"op": "演算子", "value": 値}} の形式（演算子: {ops_list}）')
    if extras:
        sep = "。" if desc and not desc.endswith("。") else ""
        desc = desc + sep + "（" + "、".join(extras) + "）"

    prop = {"description": desc}
    if len(one_of) == 1:
        prop.update(one_of[0])
    else:
        prop["oneOf"] = one_of
    return prop


def generate(func):
    """
    func: dict from tool_functions.get_full()
    Returns: dict (the tool definition for Azure OpenAI)
    """
    columns    = func.get("columns", [])
    filterable = [c for c in columns if c["is_filterable"]]
    selectable = [c for c in columns if c["is_selectable"]]

    description = func["description"]
    examples    = [e.strip() for e in func.get("usage_examples", "").splitlines() if e.strip()]
    if examples:
        description += "\n\n使用例:\n" + "\n".join(f"- {e}" for e in examples)

    select_enum = [c["column_name"] for c in selectable]

    filter_properties = {
        col["column_name"]: _build_filter_property(col)
        for col in filterable
    }

    rows_desc = func["description"].splitlines()[0] if func.get("description") else "条件に合うデータ一覧を取得する"
    query_type_desc = (
        f"rows: {rows_desc}。"
        "count: 条件に合う件数のみを取得する。countの場合、select_itemsは使用しない。"
    )

    select_base = func.get("select_description") or (
        "query_typeがrowsの場合のみ指定する。回答に必要な列だけを指定する。query_typeがcountの場合は指定しない。"
    )
    select_col_lines = [
        f"- {c['column_name']}: {c['select_items_description']}"
        for c in selectable if c.get("select_items_description")
    ]
    select_desc = select_base + ("\n" + "\n".join(select_col_lines) if select_col_lines else "")

    filters_desc = func.get("filters_description") or (
        "絞り込み条件。項目名と値を指定するとWHERE句に展開されます。"
        "%や_を含む文字列はLIKE検索、配列はIN句になります。複数項目はANDで結合されます。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["rows", "count"],
                "description": query_type_desc,
            },
            "select_items": {
                "type": "array",
                "items": {"type": "string", "enum": select_enum},
                "description": select_desc,
            },
            "filters": {
                "type": "object",
                "description": filters_desc,
                "properties": filter_properties,
            },
            "limit": {
                "type": "integer",
                "description": "最大取得件数。query_typeがcountの場合は無視する。",
                "default": func.get("limit_default", 100),
            },
        },
        "required": ["query_type", "filters"],
    }

    return {
        "type": "function",
        "function": {
            "name": func["name"],
            "description": description,
            "parameters": parameters,
        },
    }


def generate_all(funcs):
    return [generate(f) for f in funcs]


def to_json_str(func):
    return json.dumps(generate(func), ensure_ascii=False, indent=2)


def all_to_json_str(funcs):
    return json.dumps(generate_all(funcs), ensure_ascii=False, indent=2)
