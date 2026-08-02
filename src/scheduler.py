from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING

from rich.console import Console

from src.notifier.dispatcher import NotificationDispatcher

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.scraper.jd import JDScraper
    from src.storage.db import Database

console = Console()


class WatchScheduler:
    def __init__(
        self,
        config: AppConfig,
        scraper: JDScraper,
        db: Database,
    ) -> None:
        self._config = config
        self._scraper = scraper
        self._db = db
        self._dispatcher = NotificationDispatcher(config)
        self._interval = config.monitor.interval_minutes * 60
        self._running = False
        self._checks = 0
        self._alerts_sent = 0
        self._start_time: datetime | None = None

    async def start(self) -> None:
        self._start_time = datetime.now()
        self._running = True

        loop = asyncio.get_running_loop()

        def _handle_sigint() -> None:
            self._running = False

        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, _handle_sigint)

        self._print_header()

        try:
            await self._check_once()

            while self._running:
                await asyncio.sleep(self._interval)
                await self._check_once()
        except asyncio.CancelledError:
            pass
        finally:
            self._print_summary()

    async def _check_once(self) -> None:
        self._checks += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        try:
            if not await self._scraper.check_login():
                console.print(
                    f"[yellow][{timestamp}] ⚠ 登录已过期，请执行 pricemonitor login[/yellow]"
                )
                self._running = False
                return

            items = await self._scraper.fetch_cart()

            if not items:
                console.print(f"[dim][{timestamp}] 购物车为空，跳过[/dim]")
                return

            products = self._db.sync_from_cart(items)

            alerts = [
                p
                for p in products
                if p.target_price is not None and p.current_price <= p.target_price
            ]

            if alerts:
                await self._dispatcher.send_alerts(alerts)
                self._alerts_sent += len(alerts)
                count = len(products)
                console.print(
                    f"[{timestamp}] [green]检查完成[/green]  {count} 件商品  |  "
                    f"[bold red]▼ {len(alerts)} 件降价[/bold red]  通知已发送"
                )
            else:
                console.print(
                    f"[{timestamp}] [green]检查完成[/green]  {len(products)} 件商品  |  无降价"
                )
        except Exception as e:
            console.print(f"[{timestamp}] [red]检查失败: {e}[/red]")

    def _print_header(self) -> None:
        console.print("[bold cyan]启动定时监控[/bold cyan]")
        console.print(f"  间隔: {self._config.monitor.interval_minutes} 分钟")
        console.print(f"  桌面通知: {'开启' if self._config.notify.desktop.enabled else '关闭'}")
        console.print(f"  邮件通知: {'开启' if self._config.notify.email.enabled else '关闭'}")
        console.print(f"  微信通知: {'开启' if self._config.notify.wechat.enabled else '关闭'}")
        console.print("  [dim]按 Ctrl+C 退出[/dim]\n")

    def _print_summary(self) -> None:
        if self._start_time is None:
            return
        elapsed = datetime.now() - self._start_time
        minutes = int(elapsed.total_seconds() / 60)
        console.print(
            f"\n[bold]退出[/bold]  |  "
            f"共运行 {minutes} 分钟  |  "
            f"检查 {self._checks} 次  |  "
            f"发送 {self._alerts_sent} 条通知"
        )
