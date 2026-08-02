from __future__ import annotations

import asyncio

from src.config import AppConfig, load_config
from src.scraper.jd import JDScraper


async def login_jd(config: AppConfig) -> None:
    scraper = JDScraper(config)
    result = await scraper.login(headless=False)
    if result.success:
        print(f"[成功] {result.message}")
    else:
        print(f"[失败] {result.message}")


async def check_login(config: AppConfig) -> bool:
    scraper = JDScraper(config)
    return await scraper.check_login()


def main() -> None:
    config = load_config()
    asyncio.run(login_jd(config))


if __name__ == "__main__":
    main()
