"""Azure OpenAI / OpenAI API client and tool execution."""
import json
from flask import current_app
from openai import AzureOpenAI, OpenAI

from .query_builder import execute_query
from ..models.tool_functions import get_full
from . import json_generator


def _make_client():
    if current_app.config.get("IS_OPENAI_MODE"):
        endpoint = current_app.config.get("OPENAI_ENDPOINT") or None
        return OpenAI(base_url=endpoint)
    return AzureOpenAI(
        azure_endpoint=current_app.config["AZURE_OPENAI_ENDPOINT"],
        api_key=current_app.config["AZURE_OPENAI_API_KEY"],
        api_version=current_app.config["AZURE_OPENAI_API_VERSION"],
    )



def _build_tools(funcs):
    """Return (tools_for_api, tools_json_str) in OpenAI nested format."""
    tools = json_generator.generate_all(funcs)
    return tools, json.dumps(tools, ensure_ascii=False, indent=2)


def run_real(prompt, function_ids):
    funcs = [get_full(fid) for fid in function_ids]
    funcs = [f for f in funcs if f]
    tools, tools_json_str = _build_tools(funcs)

    client = _make_client()
    is_openai = current_app.config.get("IS_OPENAI_MODE")
    model = current_app.config.get("OPENAI_MODEL", "") if is_openai else current_app.config["AZURE_OPENAI_DEPLOYMENT"]
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        tool_choice="auto",
    )

    raw_response = response.model_dump()
    choice = response.choices[0]

    if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
        return {
            "mode": "real",
            "prompt": prompt,
            "tools_json": tools_json_str,
            "function_name": "",
            "tool_arguments": {},
            "executed_sql": "",
            "sql_params": [],
            "result_count": 0,
            "results": [],
            "raw_response": raw_response,
            "error": "LLMがtool_callを返しませんでした",
        }

    tool_call = choice.message.tool_calls[0]
    fn_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    return _execute_and_pack(
        mode="real",
        prompt=prompt,
        fn_name=fn_name,
        arguments=arguments,
        funcs=funcs,
        tools_json_str=tools_json_str,
        raw_response=raw_response,
    )


def run_step(messages, function_ids):
    """One step in a multi-turn tool-calling loop. Handles multiple tool_calls per response."""
    funcs = [get_full(fid) for fid in function_ids]
    funcs = [f for f in funcs if f]
    tools, tools_json_str = _build_tools(funcs)

    is_openai = current_app.config.get("IS_OPENAI_MODE")
    model = (
        current_app.config.get("OPENAI_MODEL", "") if is_openai
        else current_app.config["AZURE_OPENAI_DEPLOYMENT"]
    )

    client = _make_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    choice = response.choices[0]
    raw_response = response.model_dump()

    if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
        return {
            "type": "final",
            "content": choice.message.content or "",
            "tools_json": tools_json_str,
            "raw_response": raw_response,
        }

    assistant_message = {
        "role": "assistant",
        "content": choice.message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in choice.message.tool_calls
        ],
    }

    tool_calls_data = []
    for tool_call in choice.message.tool_calls:
        fn_name = tool_call.function.name
        tool_call_id = tool_call.id
        try:
            arguments = json.loads(tool_call.function.arguments)
        except Exception:
            arguments = {}

        func = next((f for f in funcs if f and f["name"] == fn_name), None)
        if not func:
            tool_calls_data.append({
                "tool_call_id": tool_call_id,
                "function_name": fn_name,
                "arguments": arguments,
                "error": f"関数 '{fn_name}' の定義が見つかりません",
                "results": [],
                "result_count": 0,
                "executed_sql": "",
            })
            continue

        columns = func.get("columns", [])
        selectable = [c["column_name"] for c in columns if c["is_selectable"]]
        filterable = [c["column_name"] for c in columns if c["is_filterable"]]

        columns_meta = {}
        for col in columns:
            if not col.get("is_filterable"):
                continue
            ops_str = col.get("allow_operators", "=") or "="
            ops = [op.strip() for op in ops_str.split(",") if op.strip()]
            columns_meta[col["column_name"]] = {
                "allow_like": bool(col.get("allow_like", 1)),
                "allow_array": bool(col.get("allow_array", 1)),
                "allow_operators": ops,
            }

        query_type = arguments.get("query_type", "rows")
        select_items = arguments.get("select_items") if query_type == "rows" else None
        filters = arguments.get("filters")
        limit = arguments.get("limit", func.get("limit_default", 100))

        try:
            sql, _, results = execute_query(
                db_path=current_app.config["DB_PATH"],
                target_table=func["target_table"],
                select_items=select_items,
                filters=filters,
                limit=limit,
                selectable_columns=selectable,
                filterable_columns=filterable,
                columns_meta=columns_meta,
                query_type=query_type,
            )
            tool_calls_data.append({
                "tool_call_id": tool_call_id,
                "function_name": fn_name,
                "arguments": arguments,
                "executed_sql": sql,
                "result_count": len(results),
                "results": results,
            })
        except Exception as e:
            tool_calls_data.append({
                "tool_call_id": tool_call_id,
                "function_name": fn_name,
                "arguments": arguments,
                "error": str(e),
                "results": [],
                "result_count": 0,
                "executed_sql": "",
            })

    return {
        "type": "tool_call",
        "tool_calls": tool_calls_data,
        "tools_json": tools_json_str,
        "assistant_message": assistant_message,
        "raw_response": raw_response,
    }


def run_dry(prompt, function_id, arguments):
    func = get_full(function_id)
    fn_name = func["name"] if func else ""
    funcs = [func] if func else []
    _, tools_json_str = _build_tools(funcs) if func else ([], "")

    return _execute_and_pack(
        mode="dry-run",
        prompt=prompt,
        fn_name=fn_name,
        arguments=arguments,
        funcs=funcs,
        tools_json_str=tools_json_str,
        raw_response={},
    )


def _execute_and_pack(mode, prompt, fn_name, arguments, funcs, tools_json_str, raw_response):
    func = next((f for f in funcs if f and f["name"] == fn_name), None)
    if not func:
        return {
            "mode": mode,
            "prompt": prompt,
            "tools_json": tools_json_str,
            "function_name": fn_name,
            "tool_arguments": arguments,
            "executed_sql": "",
            "sql_params": [],
            "result_count": 0,
            "results": [],
            "raw_response": raw_response,
            "error": f"関数 '{fn_name}' の定義が見つかりません",
        }

    columns    = func.get("columns", [])
    selectable = [c["column_name"] for c in columns if c["is_selectable"]]
    filterable = [c["column_name"] for c in columns if c["is_filterable"]]

    # per-column filter metadata (allow_like / allow_array / allow_operators)
    columns_meta = {}
    for col in columns:
        if not col.get("is_filterable"):
            continue
        ops_str = col.get("allow_operators", "=") or "="
        ops = [op.strip() for op in ops_str.split(",") if op.strip()]
        columns_meta[col["column_name"]] = {
            "allow_like":      bool(col.get("allow_like",  1)),
            "allow_array":     bool(col.get("allow_array", 1)),
            "allow_operators": ops,
        }

    db_path    = current_app.config["DB_PATH"]
    query_type = arguments.get("query_type", "rows")
    select_items = arguments.get("select_items") if query_type == "rows" else None
    filters      = arguments.get("filters")
    limit        = arguments.get("limit", func.get("limit_default", 100))

    sql, sql_params, results = execute_query(
        db_path=db_path,
        target_table=func["target_table"],
        select_items=select_items,
        filters=filters,
        limit=limit,
        selectable_columns=selectable,
        filterable_columns=filterable,
        columns_meta=columns_meta,
        query_type=query_type,
    )

    return {
        "mode": mode,
        "prompt": prompt,
        "tools_json": tools_json_str,
        "function_name": fn_name,
        "tool_arguments": arguments,
        "executed_sql": sql,
        "sql_params": sql_params,
        "result_count": len(results),
        "results": results,
        "raw_response": raw_response,
        "error": None,
    }
