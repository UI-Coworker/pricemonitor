from __future__ import annotations

import asyncio
import gc
from contextlib import asynccontextmanager

asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from pathlib import Path  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from src.config import AppConfig, load_config  # noqa: E402
from src.scraper.jd import JDScraper  # noqa: E402
from src.storage.db import Database  # noqa: E402


def _load_app_config() -> AppConfig:
    return load_config("config.yaml")


_db: Database | None = None
_scraper: JDScraper | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(Path("data/prices.db"))
    return _db


def get_scraper() -> JDScraper:
    global _scraper
    if _scraper is None:
        _scraper = JDScraper(_load_app_config())
    return _scraper


def get_config() -> AppConfig:
    return _load_app_config()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    gc.collect()


app = FastAPI(title="PriceMonitor API", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
