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
        """解析购物车页面，通过文本 + 商品链接提取商品信息。"""
        await page.goto(
            self.CART_URL,
            wait_until="domcontentloaded",
            timeout=self.config.monitor.page_timeout * 1000,
        )
        await page.wait_for_timeout(5000)

        # 提取所有 item.jd.com 链接及其周围文本
        items_raw = await page.evaluate("""() => {
            const items = [];
            const links = document.querySelectorAll('a[href*="item.jd.com"]');
            links.forEach(link => {
                const href = link.getAttribute('href') || '';
                const match = href.match(/item\\.jd\\.com\\/(\\d+)\\.html/);
                if (!match) return;
                const skuId = match[1];

                // 向上找容器并提取所有文本
                let container = link.closest('li, tr, [class*="item"], [class*="product"], [class*="good"]');
                if (!container) {
                    container = link.parentElement;
                    while (container && container.children.length < 6) {
                        container = container.parentElement;
                    }
                }
                const allText = container ? container.innerText : '';

                // 提取图片
                let img = '';
                const container2 = link.closest('li, tr, [class*="item"], [class*="product"]') || link.parentElement;
                if (container2) {
                    const imgEl = container2.querySelector('img');
                    if (imgEl) {
                        img = imgEl.getAttribute('src') ||
                              imgEl.getAttribute('data-src') ||
                              imgEl.getAttribute('data-lazy-img') || '';
                    }
                }

                items.push({sku_id: skuId, url: 'https:' + (href.startsWith('//') ? href : '//' + href), img: img, text: allText.slice(0, 500)});
            });
            return items;
        }""")

        return self._parse_cart_text(items_raw)

    @staticmethod
    def _parse_cart_text(items_raw: list[dict]) -> list[CartItem]:
        """从商品文本中提取名称和价格。"""
        import re

        result: list[CartItem] = []
        for item in items_raw:
            text: str = item.get("text", "")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            # 提取价格行: ¥XXXX.X到手价, ¥XXXX.X学生到手价, ¥XXXX, ¥XXXX.X
            prices: list[float] = []
            for ln in lines:
                m = re.search(r"¥\s*([\d]+(?:\.[\d]+)?)", ln)
                if m:
                    try:
                        prices.append(float(m.group(1)))
                    except ValueError:
                        pass

            # 验证: 至少有一个价格
            if not prices:
                continue

            price = prices[-1] if len(prices) >= 2 else prices[0]
            original_price = (
                prices[-2]
                if len(prices) >= 2 and prices[-2] < price
                else (None if len(prices) >= 2 else None)
            )

            # 调整: 通常第一个价格是到手价(低), 第二个是原价(高)
            if len(prices) >= 2:
                p_low = min(prices[0], prices[1])
                p_high = max(prices[0], prices[1])
                price = p_low
                original_price = p_high if p_high > p_low else None
            else:
                price = prices[0]
                original_price = None

            # 提取商品名称: 跳过价格行和"删除"行
            name_lines: list[str] = []
            skip_keywords = ("删除", "移入关注", "凑单", "领券", "已选", "有货", "自营", "申请价保")
            for ln in lines:
                if re.search(r"¥\s*\d", ln):
                    continue
                if any(kw in ln for kw in skip_keywords):
                    continue
                if len(ln) >= 2 and not ln.startswith("¥"):
                    name_lines.append(ln)

            name = (
                name_lines[0]
                if name_lines
                else name_lines[1]
                if len(name_lines) > 1
                else "未知商品"
            )

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
    def _search_cart_data(data: dict, sku_keys: tuple[str, ...]) -> list[dict]:

        def has_sku(item: dict) -> bool:
            return any(item.get(k) for k in sku_keys)

        def try_extract(arr: list) -> list[dict]:
            result: list[dict] = []
            for entry in arr:
                if not isinstance(entry, dict) or not has_sku(entry):
                    continue
                sid = next((str(entry.get(k, "")) for k in sku_keys if entry.get(k)), "")
                pname = (
                    entry.get("name")
                    or entry.get("title")
                    or entry.get("goodsName")
                    or entry.get("itemName")
                    or ""
                )
                price = entry.get("price") or entry.get("jdPrice") or entry.get("realPrice") or 0.0
                if sid and pname:
                    try:
                        price_f = float(price)
                    except (ValueError, TypeError):
                        continue
                    result.append(
                        {
                            "sku_id": sid,
                            "name": pname,
                            "url": entry.get("url", "") or f"https://item.jd.com/{sid}.html",
                            "image_url": entry.get("image", "") or entry.get("img", ""),
                            "price": price_f,
                            "original_price": float(entry.get("originalPrice", 0))
                            if entry.get("originalPrice")
                            else None,
                        }
                    )
            return result

        # 直接在顶层 data 数组中寻找
        for key in (None, "data", "result", "resultData", "Data", "body", "cartData", "cartInfo"):
            target: object = data if key is None else data.get(key)
            if isinstance(target, list):
                items = try_extract(target)
                if items:
                    return items
            if isinstance(target, dict):
                for sub_k in (
                    "list",
                    "cartList",
                    "skuList",
                    "items",
                    "itemList",
                    "rows",
                    "records",
                    "result",
                ):
                    sub: object = target.get(sub_k)
                    if isinstance(sub, list):
                        items = try_extract(sub)
                        if items:
                            return items
        return []

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
