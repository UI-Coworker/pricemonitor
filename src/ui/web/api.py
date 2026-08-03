from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from playwright.async_api import async_playwright
from pydantic import BaseModel

from src.ui.web.app import get_config, get_db, get_scraper

router = APIRouter(prefix="/api", tags=["api"])


class LoginStatusResponse(BaseModel):
    logged_in: bool
    message: str


class ProductResponse(BaseModel):
    id: int
    sku_id: str
    name: str
    url: str
    image_url: str
    current_price: float
    original_price: float | None = None
    target_price: float | None = None
    status: str
    last_checked_at: str | None = None


class SetTargetRequest(BaseModel):
    target: float | None = None


class SyncResponse(BaseModel):
    count: int
    products: list[ProductResponse]


class WatchStatusResponse(BaseModel):
    running: bool
    checks: int
    alerts_sent: int


class ConfigResponse(BaseModel):
    interval_minutes: int
    desktop_enabled: bool
    email_enabled: bool
    wechat_enabled: bool


# ── Auth ─────────────────────────────────────────────

_active_login_page: Any = None
_active_login_context: Any = None


@router.post("/login/start", response_model=LoginStatusResponse)
async def login_start() -> LoginStatusResponse:
    global _active_login_page, _active_login_context

    if _active_login_page:
        with suppress(Exception):
            await _active_login_page.close()
    if _active_login_context:
        with suppress(Exception):
            ctx = _active_login_context
            await ctx["context"].close()
            await ctx["browser"].close()
            await ctx["play"].stop()

    config = get_config()
    state_path = Path(config.jd.state_file)

    if state_path.exists():
        scraper = get_scraper()
        if await scraper.check_login():
            return LoginStatusResponse(logged_in=True, message="已登录")

    play = await async_playwright().start()
    browser = await play.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN")
    page = await ctx.new_page()

    await page.goto("https://passport.jd.com/new/login.aspx", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    screenshot_bytes = await page.screenshot(full_page=False)

    import base64

    qr = base64.b64encode(screenshot_bytes).decode()

    _active_login_page = page
    _active_login_context = {"play": play, "browser": browser, "context": ctx, "page": page}

    return LoginStatusResponse(logged_in=False, message=qr)


@router.get("/login/status", response_model=LoginStatusResponse)
async def login_status() -> LoginStatusResponse:
    global _active_login_page, _active_login_context

    if _active_login_page is None:
        scraper = get_scraper()
        logged = await scraper.check_login()
        if logged:
            return LoginStatusResponse(logged_in=True, message="已登录")
        return LoginStatusResponse(logged_in=False, message="未开始登录")

    try:
        page = _active_login_page
        url = page.url

        if "passport" not in url and "login" not in url.lower():
            config = get_config()
            state_path = Path(config.jd.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await page.context.storage_state(path=str(state_path))
            await _cleanup_login()
            return LoginStatusResponse(logged_in=True, message="登录成功")

        cookies = await page.context.cookies()
        for c in cookies:
            if c["name"] == "thor" and c.get("value"):
                config = get_config()
                state_path = Path(config.jd.state_file)
                state_path.parent.mkdir(parents=True, exist_ok=True)
                await page.context.storage_state(path=str(state_path))
                await _cleanup_login()
                return LoginStatusResponse(logged_in=True, message="登录成功")
    except Exception:
        pass

    return LoginStatusResponse(logged_in=False, message="等待扫码")


async def _cleanup_login() -> None:
    global _active_login_page, _active_login_context
    try:
        if _active_login_context:
            await _active_login_context["context"].close()
            await _active_login_context["browser"].close()
            await _active_login_context["play"].stop()
    except Exception:
        pass
    _active_login_page = None
    _active_login_context = None


# ── Products ─────────────────────────────────────────


@router.get("/products", response_model=list[ProductResponse])
async def list_products() -> list[ProductResponse]:
    db = get_db()
    products = db.list_products()
    return [_to_product_response(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int) -> ProductResponse:
    db = get_db()
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _to_product_response(product)


@router.put("/products/{product_id}/target", response_model=ProductResponse)
async def set_target(product_id: int, body: SetTargetRequest) -> ProductResponse:
    db = get_db()
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    db.update_target_price(product_id, body.target)
    updated = db.get_product(product_id)
    assert updated is not None
    return _to_product_response(updated)


@router.delete("/products/{product_id}")
async def delete_product(product_id: int) -> dict:
    db = get_db()
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    db.delete_product(product_id)
    return {"ok": True}


# ── Sync & Check ─────────────────────────────────────


@router.post("/sync", response_model=SyncResponse)
async def sync_cart() -> SyncResponse:
    scraper = get_scraper()
    db = get_db()

    if not await scraper.check_login():
        raise HTTPException(status_code=401, detail="未登录")

    items = await scraper.fetch_cart()
    if not items:
        return SyncResponse(count=0, products=[])

    products = db.sync_from_cart(items)
    return SyncResponse(
        count=len(products),
        products=[_to_product_response(p) for p in products],
    )


@router.post("/check", response_model=SyncResponse)
async def check_prices() -> SyncResponse:
    scraper = get_scraper()
    db = get_db()

    if not await scraper.check_login():
        raise HTTPException(status_code=401, detail="未登录")

    items = await scraper.fetch_cart()
    if not items:
        return SyncResponse(count=0, products=[])

    products = db.sync_from_cart(items)

    from src.notifier.dispatcher import NotificationDispatcher

    config = get_config()
    alerts = [
        p for p in products if p.target_price is not None and p.current_price <= p.target_price
    ]
    if alerts:
        dispatcher = NotificationDispatcher(config)
        await dispatcher.send_alerts(alerts)

    return SyncResponse(
        count=len(products),
        products=[_to_product_response(p) for p in products],
    )


# ── History ──────────────────────────────────────────


@router.get("/products/{product_id}/history")
async def get_history(product_id: int, limit: int = 30) -> list[dict]:
    db = get_db()
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    records = db.get_price_history(product_id, limit=limit)
    return [
        {
            "id": r.id,
            "price": r.price,
            "original_price": r.original_price,
            "source": r.source,
            "timestamp": r.timestamp,
        }
        for r in records
    ]


# ── Config ───────────────────────────────────────────


@router.get("/config", response_model=ConfigResponse)
async def api_get_config() -> ConfigResponse:
    c = get_config()
    return ConfigResponse(
        interval_minutes=c.monitor.interval_minutes,
        desktop_enabled=c.notify.desktop.enabled,
        email_enabled=c.notify.email.enabled,
        wechat_enabled=c.notify.wechat.enabled,
    )


@router.put("/config")
async def api_update_config(body: dict) -> dict:
    import yaml

    config_path = Path("config.yaml")
    with open(config_path, encoding="utf-8") as f:
        current = yaml.safe_load(f) or {}

    def deep_merge(base: dict, update: dict) -> dict:
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base.get(k), dict):
                base[k] = deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    merged = deep_merge(current, body)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(merged, f, allow_unicode=True)

    return {"ok": True}


# ── Watch ───────────────────────────────────────────


@router.post("/watch/start")
async def watch_start() -> dict:
    import src.ui.web.watch_state as ws

    ws.watch_running = True
    ws.watch_checks = 0
    ws.watch_alerts = 0
    return {"running": True}


@router.post("/watch/stop")
async def watch_stop() -> dict:
    import src.ui.web.watch_state as ws

    ws.watch_running = False
    return {"running": False}


@router.get("/watch/status")
async def watch_status() -> WatchStatusResponse:
    import src.ui.web.watch_state as ws

    return WatchStatusResponse(
        running=ws.watch_running,
        checks=ws.watch_checks,
        alerts_sent=ws.watch_alerts,
    )


# ── Helpers ──────────────────────────────────────────


def _to_product_response(p: Any) -> ProductResponse:
    return ProductResponse(
        id=p.id,
        sku_id=p.sku_id,
        name=p.name,
        url=p.url,
        image_url=p.image_url,
        current_price=p.current_price,
        original_price=p.original_price,
        target_price=p.target_price,
        status=p.status,
        last_checked_at=p.last_checked_at,
    )
