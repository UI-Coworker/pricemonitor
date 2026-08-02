from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.config import AppConfig
from src.scraper.base import LoginResult
from src.scraper.jd import JDScraper


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "jd": {"state_file": "/tmp/test_state.json", "login_timeout": 30},
            "monitor": {},
            "notify": {},
            "chart": {},
        }
    )


class TestJDScraperCheckLogin:
    @patch("src.scraper.jd.async_playwright")
    def test_check_login_no_state_file(self, mock_pw: AsyncMock, app_config: AppConfig) -> None:
        scraper = JDScraper(app_config)
        scraper._state_path = Path(app_config.jd.state_file)  # noqa: SLF001
        scraper._state_path.parent.mkdir(parents=True, exist_ok=True)  # noqa: SLF001

        import asyncio

        result = asyncio.run(scraper.check_login())
        assert result is False

    @patch("src.scraper.jd.async_playwright")
    def test_check_login_with_missing_state(
        self, mock_pw: AsyncMock, app_config: AppConfig
    ) -> None:
        from pathlib import Path

        state_path = Path("/tmp/nonexistent_state.json")
        scraper = JDScraper(app_config)
        scraper._state_path = state_path  # noqa: SLF001

        import asyncio

        result = asyncio.run(scraper.check_login())
        assert result is False


class TestJDScraperInit:
    def test_init_creates_state_dir(self, app_config: AppConfig, tmp_path) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            state_file = f"{td}/subdir/state.json"
            from src.config import ChartConfig, JDConfig, MonitorConfig, NotifyConfig

            config = AppConfig(
                jd=JDConfig(state_file=state_file),
                monitor=MonitorConfig(),
                notify=NotifyConfig(),
                chart=ChartConfig(),
            )
            scraper = JDScraper(config)
            assert scraper._state_path == Path(state_file)  # noqa: SLF001


class TestLoginResult:
    def test_success(self) -> None:
        result = LoginResult(success=True, message="OK")
        assert result.success is True
        assert result.message == "OK"

    def test_failure(self) -> None:
        result = LoginResult(success=False, message="Timeout")
        assert result.success is False
