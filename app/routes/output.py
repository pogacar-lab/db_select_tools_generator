from flask import Blueprint, render_template, Response, current_app, abort
from ..models.tool_functions import get_full, get_all
from ..services import json_generator, code_generator

bp = Blueprint("output", __name__)


@bp.route("/<int:function_id>")
def view(function_id):
    func = get_full(function_id)
    if not func:
        abort(404)
    db_path = current_app.config["DB_PATH"]
    py_code = code_generator.generate(func, db_path)
    json_str = json_generator.to_json_str(func)
    return render_template("output/view.html", func=func, py_code=py_code, json_str=json_str)


@bp.route("/<int:function_id>/python")
def download_python(function_id):
    func = get_full(function_id)
    if not func:
        abort(404)
    db_path = current_app.config["DB_PATH"]
    code = code_generator.generate(func, db_path)
    return Response(
        code,
        mimetype="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="{func["name"]}.py"'},
    )


@bp.route("/<int:function_id>/json")
def download_json(function_id):
    func = get_full(function_id)
    if not func:
        abort(404)
    json_str = json_generator.to_json_str(func)
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{func["name"]}_tool.json"'},
    )


@bp.route("/all/python")
def download_all_python():
    funcs = [get_full(f["id"]) for f in get_all()]
    db_path = current_app.config["DB_PATH"]
    code = code_generator.generate_all(funcs, db_path)
    return Response(
        code,
        mimetype="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="tools.py"'},
    )


@bp.route("/all/json")
def download_all_json():
    funcs = [get_full(f["id"]) for f in get_all()]
    json_str = json_generator.all_to_json_str(funcs)
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": 'attachment; filename="tools.json"'},
    )
