from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def fixtures_dir() -> Path:
    """返回测试 fixtures 目录路径。"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def test_config_dict() -> dict:
    """返回一份最小可用的配置字典。"""
    return {
        "jd": {
            "state_file": "data/jd_state.json",
            "login_timeout": 120,
        },
        "monitor": {
            "interval_minutes": 30,
            "page_timeout": 30,
            "request_delay": {"min": 1, "max": 3},
        },
        "notify": {
            "desktop": {"enabled": True},
            "email": {
                "enabled": False,
                "smtp_host": "smtp.qq.com",
                "smtp_port": 587,
                "sender": "",
                "password": "",
                "receivers": [],
            },
            "wechat": {
                "enabled": False,
                "provider": "pushplus",
                "pushplus_token": "",
                "serverchan_key": "",
            },
        },
        "chart": {
            "max_points": 30,
        },
    }


@pytest.fixture
def db_path(temp_dir: Path) -> Generator[Path, None, None]:
    """在临时目录中创建数据库路径。"""
    db = temp_dir / "test_prices.db"
    yield db
    if db.exists():
        db.unlink()
