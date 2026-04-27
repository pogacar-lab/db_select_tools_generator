import json
import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, abort
from ..models.tool_functions import get_all, get_full
from ..services import azure_client, history, json_generator

bp = Blueprint("apitest", __name__)


@bp.route("/")
def test_ui():
    funcs = get_all()
    is_dry_run = current_app.config["IS_DRY_RUN"]
    is_openai_mode = current_app.config["IS_OPENAI_MODE"]
    return render_template("apitest/test.html", funcs=funcs, is_dry_run=is_dry_run, is_openai_mode=is_openai_mode)


@bp.route("/run", methods=["POST"])
def run():
    data = request.get_json()
    mode = data.get("mode", "real")
    prompt = data.get("prompt", "")
    is_dry_run = current_app.config["IS_DRY_RUN"]

    if is_dry_run:
        mode = "dry-run"

    try:
        if mode == "dry-run":
            function_id = int(data.get("function_id", 0))
            arguments = data.get("arguments", {})
            result = azure_client.run_dry(prompt, function_id, arguments)
        else:
            function_ids = [int(fid) for fid in data.get("function_ids", [])]
            result = azure_client.run_real(prompt, function_ids)

        history_id = history.save(result)
        _save_api_log(result, history_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/run_step", methods=["POST"])
def run_step():
    data = request.get_json()
    messages = data.get("messages", [])
    function_ids = [int(fid) for fid in data.get("function_ids", [])]
    prompt = next((m["content"] for m in messages if m.get("role") == "user"), "")

    try:
        result = azure_client.run_step(messages, function_ids)

        if result.get("type") == "tool_call":
            for tc in result.get("tool_calls", []):
                rec = {
                    "mode": "real",
                    "prompt": prompt,
                    "function_name": tc.get("function_name", ""),
                    "tools_json": result.get("tools_json", ""),
                    "tool_arguments": tc.get("arguments", {}),
                    "executed_sql": tc.get("executed_sql", ""),
                    "sql_params": [],
                    "result_count": tc.get("result_count", 0),
                    "results": tc.get("results", []),
                    "raw_response": result.get("raw_response", {}),
                }
                history_id = history.save(rec)
                _save_api_log(rec, history_id)

        elif result.get("type") == "final":
            rec = {
                "mode": "real",
                "prompt": prompt,
                "function_name": "",
                "tools_json": result.get("tools_json", ""),
                "tool_arguments": {},
                "executed_sql": "",
                "sql_params": [],
                "result_count": 0,
                "results": [],
                "raw_response": result.get("raw_response", {}),
                "final_message": result.get("content", ""),
            }
            history_id = history.save(rec)
            _save_api_log(rec, history_id)

        return jsonify(result)
    except Exception as e:
        return jsonify({"type": "error", "error": str(e)}), 500


@bp.route("/tools-json/<int:function_id>")
def get_tools_json(function_id):
    func = get_full(function_id)
    if not func:
        abort(404)
    return jsonify(json_generator.generate(func))


@bp.route("/history")
def history_list():
    page = request.args.get("page", 1, type=int)
    rows, total = history.get_list(page=page)
    per_page = 20
    return render_template(
        "apitest/history_list.html",
        rows=rows,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@bp.route("/history/<int:history_id>")
def history_detail(history_id):
    row = history.get_by_id(history_id)
    if not row:
        abort(404)
    return render_template("apitest/history_detail.html", row=row)


@bp.route("/history/<int:history_id>/memo", methods=["POST"])
def history_memo(history_id):
    memo = request.form.get("memo", "")
    history.update_memo(history_id, memo)
    from flask import redirect, url_for, flash
    flash("メモを更新しました", "success")
    return redirect(url_for("apitest.history_detail", history_id=history_id))


def _save_api_log(result, history_id):
    log_dir = current_app.config.get("API_LOG_DIR", "./data/api_logs")
    os.makedirs(log_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(log_dir, f"{ts}_{history_id}")
    mode = result.get("mode", "")
    is_openai = current_app.config.get("IS_OPENAI_MODE")

    endpoint = (
        current_app.config.get("OPENAI_ENDPOINT", "")
        if is_openai
        else current_app.config.get("AZURE_OPENAI_ENDPOINT", "")
    )
    model = (
        current_app.config.get("OPENAI_MODEL", "")
        if is_openai
        else current_app.config.get("AZURE_OPENAI_DEPLOYMENT", "")
    )

    request_data = {
        "endpoint": endpoint,
        "api_key": "***",
        "model": model,
        "messages": [{"role": "user", "content": result.get("prompt", "")}],
        "tools": json.loads(result.get("tools_json", "[]")),
        "tool_choice": "auto",
    }
    with open(f"{base}_request.json", "w", encoding="utf-8") as f:
        json.dump(request_data, f, ensure_ascii=False, indent=2)

    if mode != "dry-run":
        with open(f"{base}_response.json", "w", encoding="utf-8") as f:
            json.dump(result.get("raw_response", {}), f, ensure_ascii=False, indent=2)


@bp.route("/history/<int:history_id>/delete", methods=["POST"])
def history_delete(history_id):
    history.delete(history_id)
    from flask import redirect, url_for, flash
    flash("削除しました", "success")
    return redirect(url_for("apitest.history_list"))
