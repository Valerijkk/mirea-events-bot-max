"""Лендинг приложения — публичная посадочная страница.

Открывается на корне `/`. Объясняет, что такое mirea-events-bot, кому он нужен и
куда идти дальше (админка, Swagger, документация в репозитории).

Намеренно `include_in_schema=False`: лендинг — не часть REST-контракта.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

landing_router = APIRouter(include_in_schema=False)


@landing_router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"bot_username": get_settings().bot_username},
    )
