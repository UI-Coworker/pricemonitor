from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.console import Console

from src.notifier.desktop import DesktopNotifier
from src.notifier.email import EmailNotifier
from src.notifier.wechat import WechatNotifier

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.storage.models import Product

console = Console()


class NotificationDispatcher:
    def __init__(self, config: AppConfig) -> None:
        self._notifiers: list = []
        if config.notify.desktop.enabled:
            self._notifiers.append(DesktopNotifier())
        if config.notify.email.enabled:
            self._notifiers.append(EmailNotifier(config.notify.email))
        if config.notify.wechat.enabled:
            self._notifiers.append(WechatNotifier(config.notify.wechat))

    async def send_alerts(self, products: list[Product]) -> None:
        alerts = [
            p for p in products if p.target_price is not None and p.current_price <= p.target_price
        ]
        if not alerts:
            return

        tasks = [n.send(p) for p in alerts for n in self._notifiers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        for p in alerts:
            console.print(
                f"[bold red]▼ 已发送通知: {p.name} ¥{p.current_price:.2f} ≤ ¥{p.target_price:.2f}[/bold red]"
            )
