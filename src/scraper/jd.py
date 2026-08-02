from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.async_api import Page, async_playwright

if TYPE_CHECKING:
    from src.config import AppConfig

from src.scraper.base import BaseScraper, CartItem, LoginResult


class JDScraper(BaseScraper):
    LOGIN_URL = "https://passport.jd.com/new/login.aspx"
    USER_HOME_URL = "https://home.jd.com/"
    QR_SELECTORS = [
        "#app > div > div.login-form > div.qrcode-login > div.qrcode-img img",
        ".qrcode-img img",
        ".login-form img[src*='qrcode']",
        "img[src*='qrCode']",
    ]

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._state_path = Path(config.jd.state_file)

    async def login(self, headless: bool = False) -> LoginResult:
        """启动浏览器并执行扫码登录流程。

        Args:
            headless: False 时会弹出浏览器窗口供用户直接扫描二维码。
        """
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
            )
            page = await context.new_page()

            try:
                await page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
                await self._wait_for_qr_code(page)

                print("请在打开的浏览器窗口中用京东 App 扫码登录...")

                await self._wait_for_login_complete(page, timeout=self.config.jd.login_timeout)

                await context.storage_state(path=str(self._state_path))
                print(f"登录成功，会话已保存至: {self._state_path}")

                return LoginResult(success=True, message="扫码登录成功")

            except TimeoutError:
                return LoginResult(success=False, message="登录超时，请重试")
            except Exception as e:
                return LoginResult(success=False, message=str(e))
            finally:
                await browser.close()

    async def check_login(self) -> bool:
        """检查保存的登录状态是否仍然有效。"""
        if not self._state_path.exists():
            return False

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=str(self._state_path),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                await page.goto(self.USER_HOME_URL, wait_until="domcontentloaded", timeout=15000)

                current_url = page.url
                if "passport" in current_url or "login" in current_url.lower():
                    return False

                page_title = await page.title()
                return "登录" not in page_title
            except Exception:
                return False
            finally:
                await browser.close()

    async def fetch_cart(self) -> list[CartItem]:
        """获取购物车商品列表。"""
        if not self._state_path.exists():
            raise RuntimeError("尚未登录，请先执行 login 命令")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=str(self._state_path),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                return await self._parse_cart_items(page)
            finally:
                await browser.close()

    async def _wait_for_qr_code(self, page: Page) -> None:
        """等待页面加载出二维码。"""
        for selector in self.QR_SELECTORS:
            try:
                await page.wait_for_selector(selector, state="visible", timeout=5000)
                return
            except Exception:
                continue
        await asyncio.sleep(2)

    async def _wait_for_login_complete(self, page: Page, timeout: int = 120) -> None:
        """等待用户完成扫码，检测页面跳转表示登录成功。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                current_url = page.url
                if "passport" not in current_url and "login" not in current_url.lower():
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
        raise TimeoutError("扫码登录超时")

    async def _parse_cart_items(self, page: Page) -> list[CartItem]:
        """解析购物车页面，提取商品信息。下一阶段实现。"""
        raise NotImplementedError("购物车解析尚未实现")
