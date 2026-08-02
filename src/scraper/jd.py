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
    CART_URL = "https://cart.jd.com/cart.action"
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
        """解析购物车页面，提取商品信息。"""
        await page.goto(
            self.CART_URL,
            wait_until="domcontentloaded",
            timeout=self.config.monitor.page_timeout * 1000,
        )

        try:
            await page.wait_for_selector(".item-form", state="visible", timeout=8000)
        except Exception:
            try:
                await page.wait_for_selector("[data-sku]", state="visible", timeout=5000)
            except Exception:
                empty_el = await page.query_selector(".cart-empty")
                if empty_el:
                    return []
                await page.wait_for_timeout(3000)

        cart_data = await page.evaluate("""() => {
            const items = [];
            const containers = document.querySelectorAll(
                '.item-form, [data-sku], .item-item, .cart-item'
            );
            containers.forEach((el) => {
                const skuId = el.getAttribute('data-sku') || '';
                if (!skuId) return;

                const linkEl =
                    el.querySelector('.item-name a') ||
                    el.querySelector('.p-name a') ||
                    el.querySelector('.p-msg a') ||
                    el.querySelector('a[href*="item.jd.com"]');
                const name = linkEl ? linkEl.textContent.trim() : '';
                const rawUrl = linkEl ? linkEl.getAttribute('href') || '' : '';
                const url = rawUrl.startsWith('//')
                    ? 'https:' + rawUrl
                    : rawUrl;

                const imgEl =
                    el.querySelector('.item-img img') ||
                    el.querySelector('.p-img img') ||
                    el.querySelector('img[src*="img"]');
                const imageUrl =
                    imgEl?.getAttribute('src') ||
                    imgEl?.getAttribute('data-src') ||
                    imgEl?.getAttribute('data-lazy-img') ||
                    '';

                const priceEl =
                    el.querySelector('.item-price .price') ||
                    el.querySelector('.p-price strong') ||
                    el.querySelector('.p-price span') ||
                    el.querySelector('.JDPrice') ||
                    el.querySelector('[class*="price"]');
                const priceText = priceEl
                    ? priceEl.textContent.trim().replace(/[^0-9.]/g, '') : '0';
                const price = parseFloat(priceText) || 0;

                const origEl = el.querySelector('.p-original, .item-origin');
                let originalPrice = null;
                if (origEl) {
                    const origText = origEl.textContent.trim().replace(/[^0-9.]/g, '');
                    originalPrice = parseFloat(origText) || null;
                }

                if (name && price > 0) {
                    items.push({
                        sku_id: skuId,
                        name: name,
                        url: url,
                        image_url: imageUrl,
                        price: price,
                        original_price: originalPrice,
                    });
                }
            });
            return items;
        }""")

        return self._normalize_cart_data(cart_data)

    @staticmethod
    def _normalize_cart_data(raw_items: list[dict]) -> list[CartItem]:
        """将 JS 提取的原始字典转为 CartItem 列表，过滤无效数据。"""
        result: list[CartItem] = []
        for item in raw_items:
            try:
                cart_item = CartItem(
                    sku_id=str(item.get("sku_id", "")).strip(),
                    name=str(item.get("name", "")).strip(),
                    url=JDScraper._normalize_product_url(str(item.get("url", ""))),
                    image_url=str(item.get("image_url", "")).strip(),
                    price=float(item.get("price", 0.0)),
                    original_price=float(item.get("original_price", 0.0))
                    if item.get("original_price") is not None
                    else None,
                )
                if cart_item.sku_id and cart_item.name and cart_item.price > 0:
                    result.append(cart_item)
            except (ValueError, TypeError):
                continue
        return result

    @staticmethod
    def _normalize_product_url(url: str) -> str:
        """补全京东商品链接为 https 完整 URL。"""
        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        parsed = url.split("?")[0]

        if "item.jd.com" in parsed:
            return parsed

        if "jd.com" in parsed:
            return parsed

        return f"https://item.jd.com/{parsed.strip('/')}.html"
