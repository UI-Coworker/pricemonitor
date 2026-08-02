from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from src.notifier.base import AbstractNotifier

if TYPE_CHECKING:
    from src.config import EmailNotifyConfig
    from src.storage.models import Product


class EmailNotifier(AbstractNotifier):
    def __init__(self, config: EmailNotifyConfig) -> None:
        self._config = config

    async def send(self, product: Product) -> None:
        if not self._config.sender or not self._config.receivers:
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self._config.sender
            msg["To"] = ", ".join(self._config.receivers)
            msg["Subject"] = f"PriceMonitor 降价提醒 - {product.name}"

            body = f"""
            <h3>▼ 降价提醒</h3>
            <p><b>{product.name}</b></p>
            <table border="1" cellpadding="6" cellspacing="0">
                <tr><td>现价</td><td style="color:red">¥{product.current_price:.2f}</td></tr>
                <tr><td>原价</td><td>¥{product.original_price:.2f}</td></tr>
                <tr><td>目标价</td><td>¥{product.target_price:.2f}</td></tr>
            </table>
            <p><a href="{product.url}">查看商品</a></p>
            """
            msg.attach(MIMEText(body, "html", "utf-8"))

            server = smtplib.SMTP(self._config.smtp_host, self._config.smtp_port, timeout=10)
            server.starttls()
            server.login(self._config.sender, self._config.password)
            server.sendmail(self._config.sender, self._config.receivers, msg.as_string())
            server.quit()
        except Exception:
            pass
