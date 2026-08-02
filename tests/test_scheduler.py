from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import (
    AppConfig,
    DesktopNotifyConfig,
    EmailNotifyConfig,
    MonitorConfig,
    NotifyConfig,
    WechatNotifyConfig,
)
from src.scheduler import WatchScheduler


def _make_config(interval_minutes: int = 30) -> AppConfig:
    return AppConfig(
        monitor=MonitorConfig(interval_minutes=interval_minutes),
        notify=NotifyConfig(
            desktop=DesktopNotifyConfig(enabled=True),
            email=EmailNotifyConfig(),
            wechat=WechatNotifyConfig(),
        ),
    )


class TestWatchScheduler:
    def test_init(self) -> None:
        config = _make_config()
        scraper = MagicMock()
        db = MagicMock()
        scheduler = WatchScheduler(config, scraper, db)
        assert scheduler._interval == 1800

    def test_check_once_no_login(self) -> None:
        config = _make_config()
        scraper = MagicMock()
        scraper.check_login = AsyncMock(return_value=False)
        db = MagicMock()

        scheduler = WatchScheduler(config, scraper, db)
        asyncio.run(scheduler._check_once())

        assert scheduler._running is False

    def test_check_once_empty_cart(self) -> None:
        config = _make_config()
        scraper = MagicMock()
        scraper.check_login = AsyncMock(return_value=True)
        scraper.fetch_cart = AsyncMock(return_value=[])
        db = MagicMock()

        scheduler = WatchScheduler(config, scraper, db)
        scheduler._running = True
        asyncio.run(scheduler._check_once())

        assert scheduler._running is True
        db.sync_from_cart.assert_not_called()

    def test_check_once_with_items(self) -> None:
        config = _make_config()
        from src.storage.models import Product

        product = Product(
            id=1,
            sku_id="123",
            name="测试",
            current_price=100.0,
            target_price=150.0,
        )

        scraper = MagicMock()
        scraper.check_login = AsyncMock(return_value=True)
        scraper.fetch_cart = AsyncMock(return_value=[MagicMock()])
        db = MagicMock()
        db.sync_from_cart.return_value = [product]

        scheduler = WatchScheduler(config, scraper, db)
        scheduler._running = True
        asyncio.run(scheduler._check_once())

        assert scheduler._checks == 1

    def test_check_once_with_alerts(self) -> None:
        config = _make_config()
        from src.storage.models import Product

        product = Product(
            id=1,
            sku_id="123",
            name="降价商品",
            current_price=50.0,
            target_price=100.0,
        )

        scraper = MagicMock()
        scraper.check_login = AsyncMock(return_value=True)
        scraper.fetch_cart = AsyncMock(return_value=[MagicMock()])
        db = MagicMock()
        db.sync_from_cart.return_value = [product]

        scheduler = WatchScheduler(config, scraper, db)
        scheduler._running = True

        with patch.object(scheduler._dispatcher, "send_alerts", new_callable=AsyncMock) as m:
            asyncio.run(scheduler._check_once())
            m.assert_called_once()
            assert scheduler._alerts_sent == 1

    def test_check_once_handles_error(self) -> None:
        config = _make_config()
        scraper = MagicMock()
        scraper.check_login = AsyncMock(side_effect=RuntimeError("网络错误"))
        db = MagicMock()

        scheduler = WatchScheduler(config, scraper, db)
        scheduler._running = True
        asyncio.run(scheduler._check_once())

        assert scheduler._checks == 1
