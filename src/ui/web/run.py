import asyncio
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from src.ui.web.app import app  # noqa: E402


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
