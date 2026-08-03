from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.ui.web.app import get_config, get_db, get_scraper

router = APIRouter()


@router.websocket("/ws/watch")
async def websocket_watch(websocket: WebSocket) -> None:
    import src.ui.web.watch_state as ws

    await websocket.accept()

    scraper = get_scraper()
    db = get_db()
    config = get_config()
    interval = config.monitor.interval_minutes * 60
    ws.watch_running = True
    ws.watch_checks = 0
    ws.watch_alerts = 0

    try:
        while ws.watch_running:
            try:
                if not await scraper.check_login():
                    await websocket.send_json({"type": "error", "message": "登录过期"})
                    break

                items = await scraper.fetch_cart()
                if items:
                    products = db.sync_from_cart(items)
                    ws.watch_checks += 1

                    alerts = [
                        p
                        for p in products
                        if p.target_price is not None and p.current_price <= p.target_price
                    ]

                    if alerts:
                        ws.watch_alerts += len(alerts)
                        from src.notifier.dispatcher import NotificationDispatcher

                        dispatcher = NotificationDispatcher(config)
                        await dispatcher.send_alerts(alerts)

                    await websocket.send_json(
                        {
                            "type": "check_result",
                            "checks": ws.watch_checks,
                            "alerts_sent": ws.watch_alerts,
                            "products": [
                                {
                                    "id": p.id,
                                    "name": p.name,
                                    "current_price": p.current_price,
                                    "target_price": p.target_price,
                                    "alert": p.target_price is not None
                                    and p.current_price <= p.target_price,
                                }
                                for p in products
                            ],
                        }
                    )
                else:
                    await websocket.send_json(
                        {
                            "type": "check_result",
                            "checks": ws.watch_checks,
                            "alerts_sent": ws.watch_alerts,
                            "products": [],
                        }
                    )
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})

            for __ in range(interval):
                await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    finally:
        ws.watch_running = False
        with suppress(Exception):
            await websocket.send_json({"type": "stopped"})
