from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from src.notifier.base import AbstractNotifier

if TYPE_CHECKING:
    from src.config import WechatNotifyConfig
    from src.storage.models import Product


class WechatNotifier(AbstractNotifier):
    def __init__(self, config: WechatNotifyConfig) -> None:
        self._config = config

    async def send(self, product: Product) -> None:
        provider = self._config.provider
        if provider == "pushplus":
            await self._send_pushplus(product)
        elif provider == "serverchan":
            await self._send_serverchan(product)

    async def _send_pushplus(self, product: Product) -> None:
        token = self._config.pushplus_token
        if not token:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    "https://www.pushplus.plus/send",
                    json={
                        "token": token,
                        "title": f"PriceMonitor 降价提醒 - {product.name}",
                        "content": self.format_message(product).replace("\n", "<br>"),
                    },
                )
        except Exception:
            pass

    async def _send_serverchan(self, product: Product) -> None:
        key = self._config.serverchan_key
        if not key:
            return
        try:
            message = self.format_message(product)
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://sctapi.ftqq.com/{key}.send",
                    data={"title": f"PriceMonitor 降价提醒 - {product.name}", "desp": message},
                )
        except Exception:
            pass
