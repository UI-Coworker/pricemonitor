from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: int = 0
    sku_id: str
    name: str
    url: str = ""
    image_url: str = ""
    current_price: float = 0.0
    original_price: float | None = None
    target_price: float | None = None
    status: str = "active"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_checked_at: str | None = None


class PriceRecord(BaseModel):
    id: int = 0
    product_id: int
    price: float
    original_price: float | None = None
    source: str = "cart"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
