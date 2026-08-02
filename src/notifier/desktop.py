from __future__ import annotations

from typing import TYPE_CHECKING

from src.notifier.base import AbstractNotifier

if TYPE_CHECKING:
    from src.storage.models import Product


class DesktopNotifier(AbstractNotifier):
    async def send(self, product: Product) -> None:
        try:
            from plyer import notification

            notification.notify(
                title="PriceMonitor 降价提醒",
                message=self.format_message(product),
                timeout=10,
            )
        except Exception:
            pass
