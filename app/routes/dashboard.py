from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from ..models.tool_functions import get_all
from ..database import get_table_schema

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    funcs = get_all()
    return render_template(
        "dashboard.html",
        funcs=funcs,
        is_dry_run=current_app.config["IS_DRY_RUN"],
    )


@bp.route("/table/<table_name>")
def table_info(table_name):
    try:
        schema = get_table_schema(table_name)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("dashboard.index"))
    return render_template("table_info.html", table_name=table_name, schema=schema)
