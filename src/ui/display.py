from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.storage.models import PriceRecord, Product

console = Console()


def print_products_table(products: list[Product]) -> None:
    if not products:
        console.print("[dim]暂无监控商品[/dim]")
        return

    table = Table(title="监控商品列表", title_style="bold cyan")
    table.add_column("ID", style="dim", width=4)
    table.add_column("商品名称", style="white", max_width=30)
    table.add_column("现价", justify="right", style="green")
    table.add_column("原价", justify="right", style="dim")
    table.add_column("目标价", justify="right", style="yellow")
    table.add_column("状态", width=6)

    for p in products:
        current = f"¥{p.current_price:.2f}"
        original = f"¥{p.original_price:.2f}" if p.original_price else "-"
        target = f"¥{p.target_price:.2f}" if p.target_price else "-"

        if p.target_price and p.current_price <= p.target_price:
            status = "[bold red]▼ 已降[/bold red]"
        elif p.status != "active":
            status = f"[dim]{p.status}[/dim]"
        else:
            status = "[green]监控中[/green]"

        table.add_row(
            str(p.id),
            _truncate(p.name, 30),
            current,
            original,
            target,
            status,
        )

    console.print(table)


def print_price_chart(records: list[PriceRecord], title: str = "价格走势") -> None:
    if not records:
        console.print("[dim]暂无价格记录[/dim]")
        return

    prices = [r.price for r in records]
    min_price = min(prices) * 0.95
    max_price = max(prices) * 1.05
    price_range = max_price - min_price or 1

    spark_chars = "▁▂▃▄▅▆▇█"
    num_chars = len(spark_chars)

    sparkline = ""
    for p in prices:
        idx = int((p - min_price) / price_range * (num_chars - 1))
        idx = max(0, min(idx, num_chars - 1))
        sparkline += spark_chars[idx]

    timestamps: list[str] = []
    for r in records:
        ts = r.timestamp[:10] if len(r.timestamp) >= 10 else r.timestamp
        timestamps.append(ts)

    unique_ts = list(dict.fromkeys(timestamps))
    date_label = " → ".join(unique_ts[:5])

    content = f"""
[bold]¥{prices[0]:.2f}[/bold] ─ 最新     [dim]¥{min_price:.0f}[/dim] ─ 最低     [dim]¥{max_price:.0f}[/dim] ─ 最高

[bold yellow]{sparkline}[/bold yellow]

{date_label}
"""
    panel = Panel(content.strip(), title=f"[bold]{title}[/bold]", border_style="cyan")
    console.print(panel)


def print_sync_summary(products: list[Product]) -> None:
    if not products:
        console.print("[dim]购物车为空或解析失败[/dim]")
        return

    table = Table(title="购物车同步结果")
    table.add_column("商品", style="white", max_width=30)
    table.add_column("现价", justify="right", style="green")
    table.add_column("原价", justify="right", style="dim")

    for p in products:
        current = f"¥{p.current_price:.2f}"
        original = f"¥{p.original_price:.2f}" if p.original_price else "-"
        table.add_row(_truncate(p.name, 30), current, original)

    console.print(table)
    console.print(f"\n[green]共 {len(products)} 件商品已同步[/green]")


def print_login_result(success: bool, message: str) -> None:
    if success:
        console.print(f"[bold green]✓ {message}[/bold green]")
    else:
        console.print(f"[bold red]✗ {message}[/bold red]")


def print_config_summary(config: AppConfig) -> None:
    table = Table(title="当前配置")
    table.add_column("项目", style="cyan")
    table.add_column("值", style="white")

    table.add_row("检查间隔", f"{config.monitor.interval_minutes} 分钟")
    table.add_row("页面超时", f"{config.monitor.page_timeout} 秒")
    table.add_row(
        "请求延迟", f"{config.monitor.request_delay.min}~{config.monitor.request_delay.max} 秒"
    )
    table.add_row("桌面通知", "开启" if config.notify.desktop.enabled else "关闭")
    table.add_row("邮件通知", "开启" if config.notify.email.enabled else "关闭")
    table.add_row("微信通知", "开启" if config.notify.wechat.enabled else "关闭")

    console.print(table)


def print_price_check_result(products: list[Product], alerts: list[Product]) -> None:
    console.print(f"\n[bold]价格检查完成[/bold] — 共 {len(products)} 件商品")

    if alerts:
        console.print("\n[bold red]▼ 价格低于目标价！[/bold red]")
        alert_table = Table()
        alert_table.add_column("商品")
        alert_table.add_column("现价", justify="right", style="red")
        alert_table.add_column("目标价", justify="right", style="yellow")
        alert_table.add_column("降幅", justify="right", style="green")

        for p in alerts:
            assert p.target_price is not None
            drop = p.target_price - p.current_price
            alert_table.add_row(
                _truncate(p.name, 25),
                f"¥{p.current_price:.2f}",
                f"¥{p.target_price:.2f}",
                f"-¥{drop:.2f}",
            )
        console.print(alert_table)
    else:
        console.print("[dim]所有商品价格均高于目标价[/dim]")


def print_check_login_status(logged_in: bool) -> None:
    if logged_in:
        console.print("[green]✓ 已登录[/green]")
    else:
        console.print("[yellow]⚠ 未登录，请先执行 [bold]pricemonitor login[/bold][/yellow]")


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
