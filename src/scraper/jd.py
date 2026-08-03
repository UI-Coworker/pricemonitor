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
        """解析购物车页面，通过页面文本'删除'分隔符 + 商品链接匹配提取。"""
        await page.goto(
            self.CART_URL,
            wait_until="domcontentloaded",
            timeout=self.config.monitor.page_timeout * 1000,
        )
        await page.wait_for_timeout(5000)

        items_raw = await page.evaluate("""() => {
            // 1) 用 '删除' / '移入关注' 切分整页文本，每节提取价格
            const fullText = document.body.innerText;
            const blocks = fullText.split(/删除|移入关注/).map(b => b.trim()).filter(b => b.length > 3);
            const pricePairs = [];
            for (const block of blocks) {
                const prices = [];
                const lines = block.split('\\n');
                for (const line of lines) {
                    const m = line.match(/[¥￥]\\s*([\\d]+(?:\\.[\\d]+)?)/);
                    if (m) prices.push(parseFloat(m[1]));
                }
                if (prices.length > 0) pricePairs.push(prices);
            }

            // 2) 提取所有 item.jd.com 链接
            const links = [];
            const seen = new Set();
            document.querySelectorAll('a[href*="item.jd.com"]').forEach(link => {
                const href = link.getAttribute('href') || '';
                const m = href.match(/item\\.jd\\.com\\/(\\d+)\\.html/);
                if (!m) return;
                const skuId = m[1];
                if (seen.has(skuId)) return;
                seen.add(skuId);

                let name = link.textContent.trim();
                if (!name) {
                    const p = link.parentElement;
                    if (p) name = p.textContent.trim().split('\\n')[0];
                }
                if (!name) return;

                let img = '';
                const box = link.closest('li, tr, [class*="item"], [class*="cart"]') || link.parentElement;
                if (box) {
                    const imgEl = box.querySelector('img');
                    if (imgEl) img = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || imgEl.getAttribute('data-lazy-img') || '';
                }

                const url = 'https:' + (href.startsWith('//') ? href : '//' + href);
                links.push({sku_id: skuId, name: name, url: url, img: img});
            });

            // 3) 按索引配对: link[i] ←→ pricePairs[i]（无价格块则兜底）
            const items = [];
            for (let i = 0; i < links.length; i++) {
                const pps = i < pricePairs.length ? pricePairs[i] : [];
                const text = pps.map(p => '¥' + p).join('\\n');
                items.push({
                    sku_id: links[i].sku_id,
                    url: links[i].url,
                    img: links[i].img,
                    name: links[i].name,
                    text: text,
                });
            }
            return items;
        }""")

        return self._parse_cart_text(items_raw)

    @staticmethod
    def _parse_cart_text(items_raw: list[dict]) -> list[CartItem]:
        """从页面文本块中提取价格。"""
        import re
        from contextlib import suppress

        result: list[CartItem] = []
        for item in items_raw:
            name = item.get("name", "")
            if not name:
                continue

            text: str = item.get("text", "")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            prices: list[float] = []
            for ln in lines:
                m = re.search(r"¥\s*([\d]+(?:\.[\d]+)?)", ln)
                if m:
                    with suppress(ValueError):
                        prices.append(float(m.group(1)))

            if not prices:
                price = 0.0
                original_price = None
            elif len(prices) >= 2:
                price = min(prices[0], prices[1])
                original_price = max(prices[0], prices[1]) if prices[0] != prices[1] else None
            else:
                price = prices[0]
                original_price = None

            result.append(
                CartItem(
                    sku_id=item["sku_id"],
                    name=name,
                    url=item.get("url", ""),
                    image_url=item.get("img", ""),
                    price=price,
                    original_price=original_price,
                )
            )

        return result

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
