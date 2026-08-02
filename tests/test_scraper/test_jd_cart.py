from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from src.config import AppConfig
from src.scraper.jd import JDScraper


@pytest.fixture
def scraper() -> JDScraper:
    config = AppConfig.model_validate(
        {
            "jd": {"state_file": "/tmp/test_state.json", "login_timeout": 30},
            "monitor": {},
            "notify": {},
            "chart": {},
        }
    )
    return JDScraper(config)


class TestNormalizeCartData:
    def test_valid_items_passed_through(self, scraper: JDScraper) -> None:
        raw = [
            {
                "sku_id": "100012345678",
                "name": "测试商品",
                "url": "//item.jd.com/100012345678.html",
                "image_url": "https://img.test.com/a.jpg",
                "price": 99.99,
                "original_price": 199.99,
            }
        ]
        result = scraper._normalize_cart_data(raw)  # noqa: SLF001
        assert len(result) == 1
        assert result[0].sku_id == "100012345678"
        assert result[0].name == "测试商品"
        assert result[0].price == 99.99
        assert result[0].original_price == 199.99

    def test_missing_name_is_filtered(self, scraper: JDScraper) -> None:
        raw = [
            {
                "sku_id": "123",
                "name": "",
                "url": "",
                "image_url": "",
                "price": 10.0,
                "original_price": None,
            }
        ]
        result = scraper._normalize_cart_data(raw)  # noqa: SLF001
        assert len(result) == 0

    def test_zero_price_is_filtered(self, scraper: JDScraper) -> None:
        raw = [
            {
                "sku_id": "123",
                "name": "零价商品",
                "url": "",
                "image_url": "",
                "price": 0.0,
                "original_price": None,
            }
        ]
        result = scraper._normalize_cart_data(raw)  # noqa: SLF001
        assert len(result) == 0

    def test_missing_sku_is_filtered(self, scraper: JDScraper) -> None:
        raw = [
            {
                "sku_id": "",
                "name": "无SKU",
                "url": "",
                "image_url": "",
                "price": 10.0,
                "original_price": None,
            }
        ]
        result = scraper._normalize_cart_data(raw)  # noqa: SLF001
        assert len(result) == 0

    def test_empty_list(self, scraper: JDScraper) -> None:
        result = scraper._normalize_cart_data([])  # noqa: SLF001
        assert result == []

    def test_sorting_is_preserved(self, scraper: JDScraper) -> None:
        raw = [
            {"sku_id": "3", "name": "C", "url": "", "image_url": "", "price": 1.0, "original_price": None},
            {"sku_id": "1", "name": "A", "url": "", "image_url": "", "price": 1.0, "original_price": None},
            {"sku_id": "2", "name": "B", "url": "", "image_url": "", "price": 1.0, "original_price": None},
        ]
        result = scraper._normalize_cart_data(raw)  # noqa: SLF001
        assert [r.sku_id for r in result] == ["3", "1", "2"]

    def test_invalid_float_is_filtered(self, scraper: JDScraper) -> None:
        raw = [
            {
                "sku_id": "123",
                "name": "异常商品",
                "url": "",
                "image_url": "",
                "price": "not_a_number",
                "original_price": None,
            }
        ]
        result = scraper._normalize_cart_data(raw)  # noqa: SLF001
        assert len(result) == 0


class TestNormalizeProductUrl:
    def test_double_slash_url(self, scraper: JDScraper) -> None:
        result = scraper._normalize_product_url("//item.jd.com/100012345678.html")  # noqa: SLF001
        assert result == "https://item.jd.com/100012345678.html"

    def test_https_url(self, scraper: JDScraper) -> None:
        result = scraper._normalize_product_url("https://item.jd.com/100012345678.html")  # noqa: SLF001
        assert result == "https://item.jd.com/100012345678.html"

    def test_url_with_query_stripped(self, scraper: JDScraper) -> None:
        result = scraper._normalize_product_url(  # noqa: SLF001
            "//item.jd.com/100012345678.html?cu=true&utm_source=a"
        )
        assert result == "https://item.jd.com/100012345678.html"

    def test_empty_url(self, scraper: JDScraper) -> None:
        result = scraper._normalize_product_url("")  # noqa: SLF001
        assert result == ""

    def test_non_jd_url(self, scraper: JDScraper) -> None:
        result = scraper._normalize_product_url("https://mall.jd.com/index-123.html")  # noqa: SLF001
        assert "mall.jd.com" in result
        assert "?" not in result


class TestParseCartItemsIntegration:
    def test_empty_cart(self, scraper: JDScraper) -> None:
        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        html_path = fixtures_dir / "jd_cart_empty.html"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(html_path.as_uri())

            empty_el = page.query_selector(".cart-empty")
            assert empty_el is not None

            browser.close()

    def test_cart_with_items(self, scraper: JDScraper) -> None:
        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        html_path = fixtures_dir / "jd_cart_items.html"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(html_path.as_uri())

            page.wait_for_selector(".item-form", state="visible")

            cart_data = page.evaluate("""() => {
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

            result = scraper._normalize_cart_data(cart_data)  # noqa: SLF001

            assert len(result) == 3

            iphone = result[0]
            assert iphone.sku_id == "100012345678"
            assert "iPhone" in iphone.name
            assert iphone.price == 9999.00
            assert iphone.original_price == 10999.00
            assert iphone.url == "https://item.jd.com/100012345678.html"

            headphone = result[1]
            assert headphone.sku_id == "100098765432"
            assert "索尼" in headphone.name
            assert headphone.price == 1999.00
            assert headphone.original_price is None

            mouse = result[2]
            assert mouse.sku_id == "100055556666"
            assert mouse.price == 499.00
            assert mouse.original_price == 699.00
            assert mouse.image_url == "https://img10.360buyimg.com/lazy3.jpg"

            browser.close()
