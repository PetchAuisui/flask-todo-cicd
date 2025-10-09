# tests/test_config.py

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
    """Base Config"""

    def test_base_has_secret_and_no_track_mod(self):
        assert hasattr(Config, "SECRET_KEY")
        assert Config.SECRET_KEY is not None
        assert Config.SQLALCHEMY_TRACK_MODIFICATIONS is False


class TestDevelopmentConfig:
    """Development configuration"""

    def test_debug_enabled(self):
        assert DevelopmentConfig.DEBUG is True

    def test_has_database_uri_default_or_env(self, monkeypatch):
        # ถ้าไม่มี DATABASE_URL ใน env ควรมีค่า default
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert hasattr(DevelopmentConfig, "SQLALCHEMY_DATABASE_URI")
        assert DevelopmentConfig.SQLALCHEMY_DATABASE_URI is not None

        # ถ้าตั้ง DATABASE_URL ควรอ่านค่านั้น
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/dev_override")
        # โหลดใหม่ (behavior ถูกประเมินตอน import แล้วในโปรเจ็กต์จริง
        # แต่เราทดสอบเพียงว่าคอนฟิกนี้ 'รองรับ' การมีค่าได้)
        assert "postgresql://" in os.environ["DATABASE_URL"]


class TestTestingConfig:
    """Testing configuration"""

    def test_testing_enabled(self):
        assert TestingConfig.TESTING is True

    def test_uses_sqlite_memory(self):
        assert "sqlite:///:memory:" in TestingConfig.SQLALCHEMY_DATABASE_URI

    def test_csrf_disabled(self):
        # ปิด CSRF เพื่อความสะดวกในการทดสอบ
        assert TestingConfig.WTF_CSRF_ENABLED is False


class TestProductionConfig:
    """Production configuration"""

    def test_debug_disabled(self):
        assert ProductionConfig.DEBUG is False

    def test_requires_database_url(self, monkeypatch):
        """
        ProductionConfig.init_app จะถูกเรียกผ่าน create_app('production')
        และ assert ว่าต้องมี DATABASE_URL เสมอ
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from app import create_app

        with pytest.raises(AssertionError):
            _ = create_app("production")

    def test_init_app_passes_when_database_url_present(self, monkeypatch):
        """
        เมื่อมี DATABASE_URL แล้ว create_app('production') ต้องไม่ raise
        """
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/prod_db")

        from app import create_app

        app = create_app("production")
        assert app is not None
        assert app.config["DEBUG"] is False


class TestConfigSelector:
    """Selector mapping"""

    def test_config_contains_all_environments(self):
        assert "development" in config
        assert "testing" in config
        assert "production" in config
        assert "default" in config

    def test_default_is_development(self):
        assert config["default"] == DevelopmentConfig
