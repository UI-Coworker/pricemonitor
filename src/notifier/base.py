from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.models import Product


class AbstractNotifier(ABC):
    @abstractmethod
    async def send(self, product: Product) -> None:
        """发送降价通知。"""

    @staticmethod
    def format_message(product: Product) -> str:
        assert product.target_price is not None
        drop = product.target_price - product.current_price
        return (
            f"▼ 降价提醒 {product.name}\n"
            f"现价: ¥{product.current_price:.2f}  目标价: ¥{product.target_price:.2f}  降幅: ¥{drop:.2f}"
        )
