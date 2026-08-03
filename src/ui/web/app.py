from __future__ import annotations

import gc
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import AppConfig, load_config
from src.scraper.jd import JDScraper
from src.storage.db import Database
from src.ui.web.api import router as api_router
from src.ui.web.ws import router as ws_router


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

app.include_router(api_router)  # type: ignore[has-type]
app.include_router(ws_router)
