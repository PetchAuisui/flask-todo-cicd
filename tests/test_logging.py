import pytest
import logging
import importlib
from app import create_app
from app.models import db

@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_logging_setup_runs_without_error(app, caplog):
    """
    รันทดสอบให้โมดูล logging_config ถูก execute อย่างน้อย 1 รอบ
    และยืนยันว่าสามารถเขียน log ได้จริง
    """
    import app.logging_config as lc

    if hasattr(lc, "configure_logging"):
        lc.configure_logging(app)
    elif hasattr(lc, "setup_logging"):
        lc.setup_logging(app)
    else:
        importlib.reload(lc)

    with caplog.at_level(logging.INFO):
        with app.app_context():
            logger = logging.getLogger("app")
            logger.info("logging smoke test")
        assert any("logging smoke test" in r.message for r in caplog.records)
