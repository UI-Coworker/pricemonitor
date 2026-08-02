from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.config import (
    AppConfig,
    DesktopNotifyConfig,
    EmailNotifyConfig,
    MonitorConfig,
    NotifyConfig,
    WechatNotifyConfig,
)
from src.notifier.base import AbstractNotifier
from src.notifier.desktop import DesktopNotifier
from src.notifier.dispatcher import NotificationDispatcher
from src.notifier.email import EmailNotifier
from src.notifier.wechat import WechatNotifier
from src.storage.models import Product


def _make_product(
    sku_id: str = "123",
    name: str = "测试商品",
    current_price: float = 50.0,
    target_price: float = 100.0,
    original_price: float | None = None,
    url: str = "",
) -> Product:
    return Product(
        sku_id=sku_id,
        name=name,
        url=url,
        current_price=current_price,
        target_price=target_price,
        original_price=original_price,
    )


class TestFormatMessage:
    def test_format_includes_prices(self) -> None:
        p = _make_product(current_price=80.0, target_price=100.0, name="测试")
        msg = AbstractNotifier.format_message(p)
        assert "80.00" in msg
        assert "100.00" in msg
        assert "20.00" in msg
        assert "测试" in msg


class TestDesktopNotifier:
    @patch("plyer.notification.notify")
    def test_send_calls_plyer(self, mock_notify: AsyncMock) -> None:
        notifier = DesktopNotifier()
        asyncio.run(notifier.send(_make_product()))
        mock_notify.assert_called_once()

    def test_send_ignores_errors(self) -> None:
        notifier = DesktopNotifier()
        asyncio.run(notifier.send(_make_product()))


class TestEmailNotifier:
    def test_skips_when_no_sender(self) -> None:
        config = EmailNotifyConfig(sender="", password="", receivers=[])
        notifier = EmailNotifier(config)
        asyncio.run(notifier.send(_make_product()))

    def test_sends_email(self) -> None:
        config = EmailNotifyConfig(sender="a@b.com", password="pwd", receivers=["r@b.com"])
        notifier = EmailNotifier(config)
        asyncio.run(notifier.send(_make_product()))


class TestWechatNotifier:
    def test_skips_when_no_token(self) -> None:
        config = WechatNotifyConfig(provider="pushplus", pushplus_token="")
        notifier = WechatNotifier(config)
        asyncio.run(notifier.send(_make_product()))

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_sends_pushplus(self, mock_post: AsyncMock) -> None:
        config = WechatNotifyConfig(provider="pushplus", pushplus_token="test_token")
        notifier = WechatNotifier(config)
        asyncio.run(notifier.send(_make_product()))
        mock_post.assert_called_once()

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_sends_serverchan(self, mock_post: AsyncMock) -> None:
        config = WechatNotifyConfig(provider="serverchan", serverchan_key="test_key")
        notifier = WechatNotifier(config)
        asyncio.run(notifier.send(_make_product()))
        mock_post.assert_called_once()


class TestDispatcher:
    def test_skips_when_no_alerts(self) -> None:
        config = AppConfig(
            monitor=MonitorConfig(),
            notify=NotifyConfig(
                desktop=DesktopNotifyConfig(enabled=True),
                email=EmailNotifyConfig(),
                wechat=WechatNotifyConfig(),
            ),
        )
        dispatcher = NotificationDispatcher(config)
        products = [_make_product(current_price=200.0, target_price=100.0)]
        asyncio.run(dispatcher.send_alerts(products))

    @patch.object(DesktopNotifier, "send", new_callable=AsyncMock)
    def test_sends_on_alert(self, mock_send: AsyncMock) -> None:
        config = AppConfig(
            monitor=MonitorConfig(),
            notify=NotifyConfig(
                desktop=DesktopNotifyConfig(enabled=True),
                email=EmailNotifyConfig(),
                wechat=WechatNotifyConfig(),
            ),
        )
        dispatcher = NotificationDispatcher(config)
        products = [_make_product(current_price=50.0, target_price=100.0, name="降价了")]
        asyncio.run(dispatcher.send_alerts(products))
        mock_send.assert_called_once()
