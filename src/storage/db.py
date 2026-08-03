from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from src.scraper.base import CartItem

from src.storage.models import PriceRecord, Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY,
    sku_id          TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    url             TEXT    DEFAULT '',
    image_url       TEXT    DEFAULT '',
    current_price   REAL    DEFAULT 0.0,
    original_price  REAL,
    target_price    REAL,
    status          TEXT    DEFAULT 'active',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS price_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    price           REAL    NOT NULL,
    original_price  REAL,
    source          TEXT    DEFAULT 'cart',
    timestamp       TEXT    NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_id
    ON price_history(product_id);

CREATE INDEX IF NOT EXISTS idx_price_history_timestamp
    ON price_history(timestamp);
"""


class Database:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    # ── Product CRUD ──────────────────────────────────────────

    def upsert_product(
        self,
        sku_id: str,
        name: str,
        url: str = "",
        image_url: str = "",
        price: float = 0.0,
        original_price: float | None = None,
    ) -> Product:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id, created_at, target_price, status FROM products WHERE sku_id = ?",
                (sku_id,),
            ).fetchone()

            if existing:
                product_id = existing["id"]
                conn.execute(
                    """UPDATE products
                       SET name = ?, url = ?, image_url = ?,
                           current_price = ?, original_price = ?,
                           updated_at = ?, last_checked_at = ?
                       WHERE id = ?""",
                    (name, url, image_url, price, original_price, now, now, product_id),
                )
                target_price = existing["target_price"]
                status = existing["status"]
                created_at = existing["created_at"]
            else:
                product_id = int(time.time() * 1_000_000)
                conn.execute(
                    """INSERT INTO products
                       (id, sku_id, name, url, image_url, current_price, original_price,
                        status, created_at, updated_at, last_checked_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (product_id, sku_id, name, url, image_url, price, original_price, now, now, now),
                )
                target_price = None
                status = "active"
                created_at = now

        return Product(
            id=product_id,
            sku_id=sku_id,
            name=name,
            url=url,
            image_url=image_url,
            current_price=price,
            original_price=original_price,
            target_price=target_price,
            status=status,
            created_at=created_at,
            updated_at=now,
            last_checked_at=now,
        )

    def get_product(self, product_id: int) -> Product | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return self._row_to_product(row)

    def get_product_by_sku(self, sku_id: str) -> Product | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM products WHERE sku_id = ?", (sku_id,)).fetchone()
        return self._row_to_product(row)

    def list_products(self, status: str | None = None) -> list[Product]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM products WHERE status = ? ORDER BY id ASC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
        result: list[Product] = []
        for r in rows:
            product = self._row_to_product(r)
            if product is not None:
                result.append(product)
        return result

    def update_target_price(self, product_id: int, target: float | None) -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET target_price = ?, updated_at = ? WHERE id = ?",
                (target, now, product_id),
            )

    def update_product_status(self, product_id: int, status: str) -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, product_id),
            )

    def delete_product(self, product_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

    # ── Price History ─────────────────────────────────────────

    def add_price_record(
        self,
        product_id: int,
        price: float,
        original_price: float | None = None,
        source: str = "cart",
    ) -> PriceRecord:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO price_history (product_id, price, original_price, source, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (product_id, price, original_price, source, now),
            )
            record_id = cursor.lastrowid
            assert record_id is not None

        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET current_price = ?, original_price = ?, last_checked_at = ?, updated_at = ? WHERE id = ?",
                (price, original_price, now, now, product_id),
            )

        return PriceRecord(
            id=record_id,
            product_id=product_id,
            price=price,
            original_price=original_price,
            source=source,
            timestamp=now,
        )

    def get_price_history(self, product_id: int, limit: int = 30) -> list[PriceRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM price_history
                   WHERE product_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (product_id, limit),
            ).fetchall()
        return [
            PriceRecord(
                id=r["id"],
                product_id=r["product_id"],
                price=r["price"],
                original_price=r["original_price"],
                source=r["source"],
                timestamp=r["timestamp"],
            )
            for r in rows
        ]

    # ── Sync ──────────────────────────────────────────────────

    def sync_from_cart(self, cart_items: list[CartItem]) -> list[Product]:
        now = datetime.now().isoformat()
        updated: list[Product] = []

        for item in cart_items:
            existing = self.get_product_by_sku(item.sku_id)
            if existing:
                product_id = existing.id
                with self._conn() as conn:
                    conn.execute(
                        """UPDATE products
                           SET name = ?, url = ?, image_url = ?,
                               current_price = ?, original_price = ?,
                               updated_at = ?, last_checked_at = ?
                           WHERE id = ?""",
                        (
                            item.name,
                            item.url,
                            item.image_url,
                            item.price,
                            item.original_price,
                            now,
                            now,
                            product_id,
                        ),
                    )
            else:
                with self._conn() as conn:
                    product_id = int(time.time() * 1_000_000)
                    conn.execute(
                        """INSERT INTO products
                           (id, sku_id, name, url, image_url, current_price, original_price,
                            status, created_at, updated_at, last_checked_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                        (
                            product_id,
                            item.sku_id,
                            item.name,
                            item.url,
                            item.image_url,
                            item.price,
                            item.original_price,
                            now,
                            now,
                            now,
                        ),
                    )

            self.add_price_record(
                product_id=product_id,
                price=item.price,
                original_price=item.original_price,
                source="cart",
            )

            product = self.get_product(product_id)
            if product:
                updated.append(product)

        return updated

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_product(row: sqlite3.Row | None) -> Product | None:
        if row is None:
            return None
        return Product(
            id=row["id"],
            sku_id=row["sku_id"],
            name=row["name"],
            url=row["url"],
            image_url=row["image_url"],
            current_price=row["current_price"],
            original_price=row["original_price"],
            target_price=row["target_price"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_checked_at=row["last_checked_at"],
        )
