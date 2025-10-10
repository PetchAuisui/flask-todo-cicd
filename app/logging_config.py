import logging
import sys


def setup_logging(app):
    """Configure application logging to stdout with a consistent format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # ล้าง handler เดิมเพื่อกันซ้ำ
    if app.logger.handlers:
        app.logger.handlers.clear()

    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    return app.logger
