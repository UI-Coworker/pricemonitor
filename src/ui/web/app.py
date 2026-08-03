from __future__ import annotations

from src.ui.web.api import router as api_router
from src.ui.web.core import app
from src.ui.web.ws import router as ws_router

app.include_router(api_router)
app.include_router(ws_router)
