import os

from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import config
from app.models import db
from app.routes import api

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)


def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)  # ผูก limiter หลังสร้าง app แล้ว

    # Register blueprints
    app.register_blueprint(api, url_prefix="/api")

    # Root endpoint
    @app.route("/")
    def index():
        return jsonify(
            {
                "message": "Flask Todo API",
                "version": "1.0.0",
                "endpoints": {"health": "/api/health", "todos": "/api/todos"},
            }
        )

    @app.route("/api/health")
    def health():
        return jsonify(status="ok"), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle all unhandled exceptions globally"""
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"success": False, "error": "Internal server error"}), 500

    # Create tables
    with app.app_context():
        db.create_all()

    return app
