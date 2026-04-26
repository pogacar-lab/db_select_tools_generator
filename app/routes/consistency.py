from flask import Blueprint, render_template, abort
from ..services.consistency import check_all, check_function

bp = Blueprint("consistency", __name__)


@bp.route("/")
def report_all():
    results = check_all()
    return render_template("consistency/report.html", results=results, single=False)


@bp.route("/<int:function_id>")
def report_one(function_id):
    result = check_function(function_id)
    if not result:
        abort(404)
    return render_template("consistency/report.html", results=[result], single=True)
