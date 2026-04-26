from flask import Flask
from .config import Config
from .database import close_db, close_history_db


def create_app():
    app = Flask(__name__)
    cfg = Config()
    app.config.from_object(cfg)
    app.config["IS_DRY_RUN"] = cfg.is_dry_run
    app.config["IS_OPENAI_MODE"] = cfg.is_openai_mode

    app.teardown_appcontext(close_db)
    app.teardown_appcontext(close_history_db)

    with app.app_context():
        from .database import init_db, init_history_db
        init_db()
        init_history_db()

    app.jinja_env.filters["enumerate"] = enumerate

    from .routes.dashboard import bp as dashboard_bp
    from .routes.editor import bp as editor_bp
    from .routes.output import bp as output_bp
    from .routes.consistency import bp as consistency_bp
    from .routes.apitest import bp as apitest_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(editor_bp, url_prefix="/tools")
    app.register_blueprint(output_bp, url_prefix="/output")
    app.register_blueprint(consistency_bp, url_prefix="/check")
    app.register_blueprint(apitest_bp, url_prefix="/apitest")

    return app
