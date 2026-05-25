"""Сканер QR под Bearer JWT — для внешних интеграций (мобильный сканер, киоск). Та же логика, что и cookie-вариант в admin/routes.py."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentOrganizer, DbSession
from app.core.rate_limit import scan_limiter
from app.schemas.scan import ScanRequest, ScanResponse
from app.services.scan import scan_lookup

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post(
    "",
    summary="Отметить посещение по QR или коду",
    description=(
        "Принимает значение из QR-картинки (qr_token, 32 hex) ИЛИ короткий "
        "код записи (RG-XXXXXX из текста бота). Возвращает один из четырёх "
        "результатов в поле `status`:\n\n"
        "* `ok` — запись только что помечена `attended`, пускайте гостя;\n"
        "* `already_attended` — этот пропуск уже использовали раньше (в "
        "`attended_at` — время первого прохода);\n"
        "* `cancelled` — запись отменена (пользователем / организатором / "
        "поздно), пускать нельзя;\n"
        "* `not_found` — qr_token/code в системе не существует.\n\n"
        "При попытке сканировать чужое мероприятие — 403."
    ),
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
)
async def scan_qr(
    payload: ScanRequest,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> ScanResponse:
    # Brute-force защита: 60/мин на организатора — реальному оператору хватает, скрипту перебора RG-XXXXXX/32-hex не хватит.
    if not scan_limiter.check(f"scan:{organizer.id}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком частые запросы сканера. Подождите минуту.",
        )
    return await scan_lookup(session, organizer, payload.qr_token)
