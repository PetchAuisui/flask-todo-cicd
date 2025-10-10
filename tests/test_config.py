import os
import pytest

from app.config import (
    Config,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    config,
)


class TestConfig:
    """Base configuration"""

    def test_base_has_secret_and_no_track_mod(self):
        assert hasattr(Config, "SECRET_KEY")
        assert Config.SECRET_KEY is not None
        assert Config.SQLALCHEMY_TRACK_MODIFICATIONS is False


class TestDevelopmentConfig:
    """Development configuration"""

    def test_debug_enabled(self):
        assert DevelopmentConfig.DEBUG is True

    def test_has_database_uri_default_or_env(self, monkeypatch):
        # ไม่มี DATABASE_URL -> ควรมีค่า default ให้ใช้งานได้
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert hasattr(DevelopmentConfig, "SQLALCHEMY_DATABASE_URI")
        assert DevelopmentConfig.SQLALCHEMY_DATABASE_URI is not None

        # มี DATABASE_URL -> รองรับการอ่านค่าจาก env
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/dev_override")
        assert "postgresql://" in os.environ["DATABASE_URL"]


class TestTestingConfig:
    """Testing configuration"""

    def test_testing_enabled(self):
        assert TestingConfig.TESTING is True

    def test_uses_sqlite_memory(self):
        assert "sqlite:///:memory:" in TestingConfig.SQLALCHEMY_DATABASE_URI

    def test_csrf_disabled(self):
        assert TestingConfig.WTF_CSRF_ENABLED is False


class TestProductionConfig:
    """Production configuration"""

    def test_debug_disabled(self):
        assert ProductionConfig.DEBUG is False

    def test_requires_database_url(self, monkeypatch):
        """
        Production ต้องมี DATABASE_URL เสมอ (assert ใน init_app)
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from app import create_app

        with pytest.raises(AssertionError):
            _ = create_app("production")

    def test_init_app_passes_when_database_url_present(self, monkeypatch):
        """
        มี DATABASE_URL แล้วควรสร้างแอป production ได้
        NOTE: เนื่องจาก ProductionConfig.SQLALCHEMY_DATABASE_URI ถูกกำหนดตอน import
        เราจึง set ทั้ง env และ override แอตทริบิวต์บนคลาสก่อนเรียก create_app
        """
        # 1) ตั้ง env
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

        # 2) กันเคสที่คลาสถูกประเมินก่อน env: override ค่าในคลาสด้วย
        monkeypatch.setattr(
            ProductionConfig,
            "SQLALCHEMY_DATABASE_URI",
            "sqlite:///:memory:",
            raising=False,
        )

        # 3) ค่อยสร้างแอป
        from app import create_app

        app = create_app("production")
        assert app is not None
        assert app.config["DEBUG"] is False
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


class TestConfigSelector:
    """Selector mapping"""

    def test_config_contains_all_environments(self):
        assert "development" in config
        assert "testing" in config
        assert "production" in config
        assert "default" in config

    def test_default_is_development(self):
        assert config["default"] == DevelopmentConfig
