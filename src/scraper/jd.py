from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.async_api import Page, Response, async_playwright

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
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    return

                cookies = await page.context.cookies()
                for c in cookies:
                    if c["name"] == "thor" and c.get("value"):
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                        return
            except Exception:
                pass
            await asyncio.sleep(2)
        raise TimeoutError("扫码登录超时")

    async def _parse_cart_items(self, page: Page) -> list[CartItem]:
        """解析购物车页面，提取商品信息。

        策略优先级：
        1. 拦截购物车 XHR/API 响应中的 JSON 数据
        2. 从页面 window 全局对象提取
        3. DOM 解析（适配多种选择器）
        """
        api_cart_items: list[dict] = []
        api_response_sources: list[str] = []

        async def capture_response(response: Response) -> None:
            url = response.url
            if any(
                keyword in url.lower()
                for keyword in ("cart", "getcart", "GetCartDetail", "cartGets", "getCarts")
            ):
                try:
                    body = await response.json()
                    if isinstance(body, dict):
                        api_cart_items.append(body)
                        api_response_sources.append(url)
                except Exception:
                    pass

        page.on("response", capture_response)

        try:
            await page.goto(
                self.CART_URL,
                wait_until="domcontentloaded",
                timeout=self.config.monitor.page_timeout * 1000,
            )

            await page.wait_for_timeout(6000)

        finally:
            page.remove_listener("response", capture_response)

        if api_cart_items:
            extracted = self._extract_from_api(api_cart_items)
            if extracted:
                return self._normalize_cart_data(extracted)

        js_data = await page.evaluate("""() => {
            const checkout = (obj) => {
                if (!obj || typeof obj !== 'object') return null;
                if (Array.isArray(obj) && obj.length > 0) {
                    const first = obj[0];
                    if (first && first.skuId) return obj;
                    if (first && first.sku) return obj;
                    if (first && first.SkuId) return obj;
                }
                for (const key of Object.keys(obj)) {
                    if (Array.isArray(obj[key]) && obj[key].length > 0) {
                        const item = obj[key][0];
                        if (item && typeof item === 'object' &&
                            (item.skuId || item.sku || item.SkuId ||
                             item.cartItem || item.itemId)) {
                            return obj[key];
                        }
                    }
                }
                return null;
            };
            const globals = ['__PRELOADED_STATE__', '__NUXT__', '__REDUX_STORE__',
                             'pageData', '_pageData', '__INITIAL_STATE__',
                             '__NEXT_DATA__', '__APP_STATE__'];
            for (const name of globals) {
                if (window[name]) {
                    const data = checkout(window[name]);
                    if (data) return {source: name, data: data};
                }
            }
            for (const key of Object.keys(window)) {
                if (key.toLowerCase().includes('cart')) continue;
                try {
                    const val = window[key];
                    const data = checkout(val);
                    if (data) return {source: key, data: data};
                } catch(e) {}
            }
            return null;
        }""")
        if js_data and isinstance(js_data, dict):
            items = self._extract_from_js_global(js_data)
            if items:
                return self._normalize_cart_data(items)

        try:
            await page.wait_for_selector(".item-form", state="visible", timeout=5000)
        except Exception:
            try:
                await page.wait_for_selector("[data-sku]", state="visible", timeout=5000)
            except Exception:
                empty_el = await page.query_selector(".cart-empty")
                if empty_el:
                    return []
                await page.wait_for_timeout(2000)

        dom_data = await page.evaluate("""() => {
            const items = [];
            const containerSelectors = [
                '.item-form', '[data-sku]:not([data-sku=""])', '.item-item',
                '.cart-item', '.good-item', '.product-item',
                '[class*="cart"] [class*="item"]',
                'li[data-sku]', 'div[data-sku]',
                '.sku-item', '[id*="product"]',
            ];
            let containers = [];
            for (const sel of containerSelectors) {
                containers = Array.from(document.querySelectorAll(sel));
                if (containers.length > 0) break;
            }

            if (containers.length === 0) {
                containers = Array.from(document.querySelectorAll(
                    'a[href*="item.jd.com"]'
                )).map(el => el.closest('li, div[class], tr'));
            }

            containers.forEach((el) => {
                const skuId =
                    el.getAttribute('data-sku') ||
                    el.getAttribute('data-id') ||
                    el.getAttribute('sku') ||
                    '';

                const linkEl =
                    el.querySelector('.item-name a') ||
                    el.querySelector('.p-name a') ||
                    el.querySelector('.p-msg a') ||
                    el.querySelector('a[href*="item.jd.com"]') ||
                    el.querySelector('a[href*="product"]');
                const name = linkEl ? linkEl.textContent.trim() : '';
                const rawUrl = linkEl ? linkEl.getAttribute('href') || '' : '';
                const url = rawUrl.startsWith('//') ? 'https:' + rawUrl : rawUrl;

                const imgEl =
                    el.querySelector('.item-img img') ||
                    el.querySelector('.p-img img') ||
                    el.querySelector('img[src*="img"]') ||
                    el.querySelector('img[src*="cdn"]');
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
                    el.querySelector('[class*="price"]') ||
                    el.querySelector('[class*="Price"]');
                const priceText = priceEl
                    ? priceEl.textContent.trim().replace(/[^0-9.]/g, '') : '0';
                const price = parseFloat(priceText) || 0;

                const origEl = el.querySelector(
                    '.p-original, .item-origin, [class*="ori"], [class*="origin"], del, .old-price'
                );
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

        return self._normalize_cart_data(dom_data)

    @staticmethod
    def _extract_from_api(responses: list[dict]) -> list[dict]:
        """从捕获的 API 响应中提取购物车数据。"""
        items: list[dict] = []
        for resp in responses:
            flat = str(resp)
            for key in ("skuList", "cartList", "CartInfo", "cart", "list", "data", "result"):
                val = resp.get(key)
                if isinstance(val, list):
                    for entry in val:
                        if not isinstance(entry, dict):
                            continue
                        sid = entry.get("skuId") or entry.get("sku") or entry.get("SkuId") or ""
                        pname = (
                            entry.get("name")
                            or entry.get("title")
                            or entry.get("itemName")
                            or entry.get("goodsName")
                            or entry.get("Name")
                            or ""
                        )
                        price_val = (
                            entry.get("price")
                            or entry.get("jdPrice")
                            or entry.get("skuPrice")
                            or entry.get("Price")
                            or entry.get("realPrice")
                        )
                        if sid and pname and price_val is not None:
                            try:
                                price = float(price_val)
                            except (ValueError, TypeError):
                                continue
                            items.append(
                                {
                                    "sku_id": str(sid),
                                    "name": str(pname),
                                    "url": entry.get("url", "") or entry.get("Url", ""),
                                    "image_url": entry.get("img", "")
                                    or entry.get("image", "")
                                    or entry.get("Img", "")
                                    or "",
                                    "price": price,
                                    "original_price": (
                                        float(entry.get("originalPrice", 0))
                                        if entry.get("originalPrice")
                                        else None
                                    ),
                                }
                            )
                if items:
                    break
            if items:
                break
            if len(flat) > 50 and "skuId" in flat:
                pass

        return items

    @staticmethod
    def _extract_from_js_global(data: dict) -> list[dict]:
        """从 JS 全局对象中提取购物车数据。"""
        raw = data.get("data", data)
        if not isinstance(raw, list):
            return []

        items: list[dict] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            sid = entry.get("skuId") or entry.get("sku") or entry.get("SkuId") or ""
            pname = (
                entry.get("name")
                or entry.get("title")
                or entry.get("itemName")
                or entry.get("goodsName")
                or ""
            )
            price_val = (
                entry.get("price")
                or entry.get("jdPrice")
                or entry.get("skuPrice")
                or entry.get("realPrice")
            )
            if sid and pname and price_val is not None:
                try:
                    price = float(price_val)
                except (ValueError, TypeError):
                    continue
                items.append(
                    {
                        "sku_id": str(sid),
                        "name": str(pname),
                        "url": entry.get("url", "") or f"https://item.jd.com/{sid}.html",
                        "image_url": entry.get("img", "") or entry.get("image", "") or "",
                        "price": price,
                        "original_price": (
                            float(entry.get("originalPrice", 0))
                            if entry.get("originalPrice")
                            else None
                        ),
                    }
                )
        return items

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
