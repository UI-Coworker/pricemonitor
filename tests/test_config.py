from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path

from src.config import AppConfig, load_config


class TestAppConfig:
    def test_default_values(self) -> None:
        data = {"jd": {}, "monitor": {}, "notify": {}, "chart": {}}
        config = AppConfig.model_validate(data)
        assert config.jd.login_timeout == 120
        assert config.monitor.interval_minutes == 30
        assert config.notify.desktop.enabled is True
        assert config.notify.email.enabled is False
        assert config.notify.wechat.enabled is False

    def test_full_config(self, test_config_dict: dict) -> None:
        config = AppConfig.model_validate(test_config_dict)
        assert config.jd.state_file == "data/jd_state.json"
        assert config.monitor.request_delay.min == 1.0
        assert config.monitor.request_delay.max == 3.0

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        config_data = {
            "jd": {"state_file": str(tmp_path / "state.json")},
            "monitor": {"interval_minutes": 60},
            "notify": {"desktop": {"enabled": False}},
            "chart": {"max_points": 50},
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_path))
        assert config.monitor.interval_minutes == 60
        assert config.notify.desktop.enabled is False
        assert config.chart.max_points == 50

    def test_load_config_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.yaml")


class TestJDConfig:
    def test_jd_state_file_default(self) -> None:
        from src.config import JDConfig

        config = JDConfig()
        assert config.state_file == "data/jd_state.json"
        assert config.login_timeout == 120
