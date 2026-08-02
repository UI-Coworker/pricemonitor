from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CartItem:
    sku_id: str
    name: str
    url: str
    image_url: str
    price: float
    original_price: float | None = None


@dataclass
class LoginResult:
    success: bool
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class BaseScraper(ABC):
    @abstractmethod
    async def login(self) -> LoginResult:
        """执行登录流程，返回登录结果。"""

    @abstractmethod
    async def check_login(self) -> bool:
        """检查当前是否处于登录状态。"""

    @abstractmethod
    async def fetch_cart(self) -> list[CartItem]:
        """获取购物车中的商品列表。"""
