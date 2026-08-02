from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.scraper.base import CartItem
from src.storage.db import Database


@pytest.fixture
def db(temp_dir: Path) -> Database:
    db_path = temp_dir / "test_prices.db"
    return Database(db_path)


@pytest.fixture
def sample_cart_items() -> list[CartItem]:
    return [
        CartItem(
            sku_id="100012345678",
            name="iPhone 15 Pro Max",
            url="https://item.jd.com/100012345678.html",
            image_url="https://img.jd.com/iphone.jpg",
            price=9999.00,
            original_price=10999.00,
        ),
        CartItem(
            sku_id="100098765432",
            name="索尼 WH-1000XM5",
            url="https://item.jd.com/100098765432.html",
            image_url="https://img.jd.com/sony.jpg",
            price=1999.00,
            original_price=None,
        ),
        CartItem(
            sku_id="100055556666",
            name="罗技 MX Master 3S",
            url="https://item.jd.com/100055556666.html",
            image_url="https://img.jd.com/logi.jpg",
            price=499.00,
            original_price=699.00,
        ),
    ]


class TestDatabaseInit:
    def test_creates_db_file(self, temp_dir: Path) -> None:
        db_path = temp_dir / "new.db"
        assert not db_path.exists()
        Database(db_path)
        assert db_path.exists()

    def test_creates_parent_dirs(self, temp_dir: Path) -> None:
        db_path = temp_dir / "sub" / "dir" / "test.db"
        Database(db_path)
        assert db_path.exists()


class TestProductCRUD:
    def test_upsert_inserts_new_product(self, db: Database) -> None:
        product = db.upsert_product(
            sku_id="test-001",
            name="测试商品",
            url="https://item.jd.com/test-001.html",
            price=100.0,
            original_price=150.0,
        )
        assert product.id > 0
        assert product.sku_id == "test-001"
        assert product.name == "测试商品"
        assert product.current_price == 100.0
        assert product.original_price == 150.0
        assert product.status == "active"

    def test_upsert_updates_existing_product(self, db: Database) -> None:
        first = db.upsert_product(sku_id="test-002", name="原名", price=50.0)
        second = db.upsert_product(sku_id="test-002", name="新名", price=30.0)

        assert second.id == first.id
        assert second.name == "新名"
        assert second.current_price == 30.0
        assert db.get_product(first.id).name == "新名"

    def test_get_product_by_id(self, db: Database) -> None:
        created = db.upsert_product(sku_id="test-003", name="商品", price=10.0)
        found = db.get_product(created.id)
        assert found is not None
        assert found.sku_id == "test-003"

    def test_get_product_not_found(self, db: Database) -> None:
        assert db.get_product(99999) is None

    def test_get_product_by_sku(self, db: Database) -> None:
        db.upsert_product(sku_id="test-004", name="商品", price=10.0)
        found = db.get_product_by_sku("test-004")
        assert found is not None
        assert found.name == "商品"
        assert found.sku_id == "test-004"

    def test_list_products_all(self, db: Database, sample_cart_items: list[CartItem]) -> None:
        for item in sample_cart_items:
            db.upsert_product(
                sku_id=item.sku_id,
                name=item.name,
                url=item.url,
                image_url=item.image_url,
                price=item.price,
                original_price=item.original_price,
            )

        products = db.list_products()
        assert len(products) == 3

    def test_list_products_filter_by_status(
        self, db: Database, sample_cart_items: list[CartItem]
    ) -> None:
        for item in sample_cart_items:
            db.upsert_product(
                sku_id=item.sku_id,
                name=item.name,
                url=item.url,
                image_url=item.image_url,
                price=item.price,
                original_price=item.original_price,
            )

        product = db.get_product_by_sku("100012345678")
        assert product is not None
        db.update_product_status(product.id, "paused")

        active = db.list_products(status="active")
        paused = db.list_products(status="paused")

        assert len(active) == 2
        assert len(paused) == 1
        assert paused[0].sku_id == "100012345678"

    def test_update_target_price(self, db: Database) -> None:
        product = db.upsert_product(sku_id="test-005", name="商品", price=100.0)
        assert product.target_price is None

        db.update_target_price(product.id, 80.0)
        updated = db.get_product(product.id)
        assert updated is not None
        assert updated.target_price == 80.0

        db.update_target_price(product.id, None)
        cleared = db.get_product(product.id)
        assert cleared is not None
        assert cleared.target_price is None

    def test_delete_product(self, db: Database) -> None:
        product = db.upsert_product(sku_id="test-006", name="待删除", price=10.0)
        db.delete_product(product.id)
        assert db.get_product(product.id) is None

    def test_empty_list(self, db: Database) -> None:
        assert db.list_products() == []


class TestPriceHistory:
    def test_add_and_retrieve_price_record(self, db: Database) -> None:
        product = db.upsert_product(sku_id="test-007", name="商品", price=100.0)

        record = db.add_price_record(product.id, price=95.0, original_price=120.0, source="cart")
        assert record.id > 0
        assert record.price == 95.0
        assert record.original_price == 120.0
        assert record.source == "cart"

        updated = db.get_product(product.id)
        assert updated is not None
        assert updated.current_price == 95.0
        assert updated.original_price == 120.0

    def test_price_history_limit(self, db: Database) -> None:
        product = db.upsert_product(sku_id="test-008", name="商品", price=200.0)

        for i in range(35):
            db.add_price_record(product.id, price=200.0 - i, source="cart")

        records = db.get_price_history(product.id, limit=30)
        assert len(records) == 30
        assert records[0].price == 166.0

    def test_empty_history(self, db: Database) -> None:
        product = db.upsert_product(sku_id="test-009", name="无记录", price=10.0)
        records = db.get_price_history(product.id)
        assert records == []

    def test_cascade_delete_removes_history(self, db: Database) -> None:
        product = db.upsert_product(sku_id="test-010", name="商品", price=50.0)
        db.add_price_record(product.id, price=50.0)

        db.delete_product(product.id)
        records = db.get_price_history(product.id)
        assert records == []


class TestSyncFromCart:
    def test_sync_new_items(self, db: Database, sample_cart_items: list[CartItem]) -> None:
        products = db.sync_from_cart(sample_cart_items)
        assert len(products) == 3

        for item in sample_cart_items:
            product = db.get_product_by_sku(item.sku_id)
            assert product is not None
            assert product.name == item.name
            assert product.current_price == item.price

            history = db.get_price_history(product.id)
            assert len(history) == 1

    def test_sync_updates_existing_items(self, db: Database) -> None:
        first_sync = [
            CartItem(
                sku_id="100012345678",
                name="iPhone 15",
                url="https://item.jd.com/100012345678.html",
                image_url="",
                price=9999.00,
                original_price=10999.00,
            )
        ]

        db.sync_from_cart(first_sync)
        product = db.get_product_by_sku("100012345678")
        assert product is not None
        assert product.name == "iPhone 15"

        second_sync = [
            CartItem(
                sku_id="100012345678",
                name="iPhone 15 Pro Max",
                url="https://item.jd.com/100012345678.html",
                image_url="",
                price=8999.00,
                original_price=9999.00,
            )
        ]

        db.sync_from_cart(second_sync)
        updated = db.get_product_by_sku("100012345678")
        assert updated is not None
        assert updated.name == "iPhone 15 Pro Max"
        assert updated.current_price == 8999.00

        history = db.get_price_history(product.id)
        assert len(history) == 2

    def test_sync_with_empty_cart(self, db: Database) -> None:
        products = db.sync_from_cart([])
        assert products == []

    def test_product_sequence_is_preserved(self, db: Database) -> None:
        db.upsert_product(sku_id="existing-01", name="已有商品", price=10.0)
        existing = db.get_product_by_sku("existing-01")
        assert existing is not None

        cart_items = [
            CartItem(
                sku_id="existing-01",
                name="已有商品更新",
                url="",
                image_url="",
                price=15.0,
                original_price=None,
            )
        ]

        products = db.sync_from_cart(cart_items)
        assert len(products) == 1
        assert products[0].current_price == 15.0
