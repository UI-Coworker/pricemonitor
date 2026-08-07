from __future__ import annotations

import asyncio
from pathlib import Path

import click

from src.config import load_config
from src.notifier.dispatcher import NotificationDispatcher
from src.scheduler import WatchScheduler
from src.scraper.jd import JDScraper
from src.storage.db import Database
from src.ui.display import (
    console,
    print_check_login_status,
    print_config_summary,
    print_login_result,
    print_price_chart,
    print_price_check_result,
    print_products_table,
    print_sync_summary,
)


def _get_db(config_path: str) -> Database:
    return Database(Path("data/prices.db"))


def _get_scraper(config_path: str) -> JDScraper:
    config = load_config(config_path)
    return JDScraper(config)


@click.group()
@click.option("--config", "-c", default="config.yaml", help="配置文件路径")
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.pass_context
def login(ctx: click.Context) -> None:
    """扫码登录京东，保存登录会话"""
    config_path: str = ctx.obj["config_path"]
    scraper = _get_scraper(config_path)

    async def _run() -> None:
        result = await scraper.login(headless=False)
        print_login_result(result.success, result.message)

    asyncio.run(_run())


@cli.command()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """同步购物车商品到监控数据库"""
    config_path: str = ctx.obj["config_path"]
    scraper = _get_scraper(config_path)
    db = _get_db(config_path)

    async def _run() -> None:
        logged_in = await scraper.check_login()
        if not logged_in:
            console.print("[yellow]⚠ 尚未登录，请先执行 [bold]pricemonitor login[/bold][/yellow]")
            return

        console.print("[cyan]正在获取购物车数据...[/cyan]")
        items = await scraper.fetch_cart()

        if not items:
            console.print("[dim]购物车为空，请先在京东购物车中添加商品[/dim]")
            return

        products = db.sync_from_cart(items)
        print_sync_summary(products)

    asyncio.run(_run())


@cli.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """列出所有监控中的商品"""
    db = _get_db(ctx.obj["config_path"])
    products = db.list_products()
    print_products_table(products)


@cli.command()
@click.argument("product_id", type=int)
@click.argument("price", type=float)
@click.pass_context
def target(ctx: click.Context, product_id: int, price: float) -> None:
    """设置商品目标价，低于此价时触发提醒"""
    db = _get_db(ctx.obj["config_path"])
    product = db.get_product(product_id)

    if product is None:
        console.print(f"[red]商品 ID {product_id} 不存在[/red]")
        raise SystemExit(1)

    db.update_target_price(product_id, price)
    console.print(
        f"[green]✓ {product.name}[/green] 目标价已设为 [bold yellow]¥{price:.2f}[/bold yellow]"
    )


@cli.command()
@click.option("--reset", is_flag=True, help="清除目标价")
@click.argument("product_id", type=int)
@click.pass_context
def untarget(ctx: click.Context, product_id: int, reset: bool) -> None:
    """清除商品的目标价（--reset 已默认）"""
    db = _get_db(ctx.obj["config_path"])
    product = db.get_product(product_id)

    if product is None:
        console.print(f"[red]商品 ID {product_id} 不存在[/red]")
        raise SystemExit(1)

    db.update_target_price(product_id, None)
    console.print(f"[green]✓ {product.name}[/green] 目标价已清除")


@cli.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """立即检查一次所有监控商品的价格"""
    config_path: str = ctx.obj["config_path"]
    scraper = _get_scraper(config_path)
    db = _get_db(config_path)

    async def _run() -> None:
        logged_in = await scraper.check_login()
        print_check_login_status(logged_in)

        if not logged_in:
            return

        console.print("[cyan]正在获取购物车最新价格...[/cyan]")
        items = await scraper.fetch_cart()

        if not items:
            console.print("[dim]购物车为空，请先在京东购物车中添加商品[/dim]")
            return

        products = db.sync_from_cart(items)

        alerts = [
            p for p in products if p.target_price is not None and p.current_price <= p.target_price
        ]

        print_price_check_result(products, alerts)

        if alerts:
            app_config = load_config(config_path)
            dispatcher = NotificationDispatcher(app_config)
            await dispatcher.send_alerts(alerts)

    asyncio.run(_run())


@cli.command()
@click.pass_context
def watch(ctx: click.Context) -> None:
    """启动持续监控，定时检查价格并发送降价通知"""
    config_path: str = ctx.obj["config_path"]
    app_config = load_config(config_path)
    scraper = _get_scraper(config_path)
    db = _get_db(config_path)

    async def _run() -> None:
        logged_in = await scraper.check_login()
        if not logged_in:
            console.print("[yellow]⚠ 尚未登录，请先执行 [bold]pricemonitor login[/bold][/yellow]")
            return

        scheduler = WatchScheduler(app_config, scraper, db)
        await scheduler.start()

    asyncio.run(_run())


@cli.command()
@click.argument("product_id", type=int)
@click.option("-n", "--num", default=30, help="显示记录数")
@click.pass_context
def history(ctx: click.Context, product_id: int, num: int) -> None:
    """查看商品价格走势"""
    db = _get_db(ctx.obj["config_path"])
    product = db.get_product(product_id)

    if product is None:
        console.print(f"[red]商品 ID {product_id} 不存在[/red]")
        raise SystemExit(1)

    records = db.get_price_history(product_id, limit=num)
    print_price_chart(records, title=product.name)


@cli.command()
@click.argument("product_id", type=int)
@click.pass_context
def remove(ctx: click.Context, product_id: int) -> None:
    """移除商品监控"""
    db = _get_db(ctx.obj["config_path"])
    product = db.get_product(product_id)

    if product is None:
        console.print(f"[red]商品 ID {product_id} 不存在[/red]")
        raise SystemExit(1)

    product_name = product.name
    db.delete_product(product_id)
    console.print(f"[green]✓ {product_name}[/green] 已移除")

    history_db = _get_db(ctx.obj["config_path"])
    records = history_db.get_price_history(product_id)
    console.print(f"  共删除 {len(records)} 条历史记录")


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """查看当前配置"""
    config_path: str = ctx.obj["config_path"]
    config_data = load_config(config_path)
    print_config_summary(config_data)


if __name__ == "__main__":
    cli()
