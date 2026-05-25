"""URL-билдеры. Имена выровнены под architecture.md §4.1."""
from __future__ import annotations

from config.settings import get_settings

API_V1 = "/api/v1"


def _base() -> str:
    return str(get_settings().base_url).rstrip("/")


def api_url(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return _base() + path


def spa_url(path: str = "") -> str:
    suffix = path if path.startswith("/") or not path else "/" + path
    return _base() + suffix


# REST API
def api_healthz() -> str: return api_url(f"{API_V1}/healthz")
def api_readyz() -> str: return api_url(f"{API_V1}/readyz")
def api_login() -> str: return api_url(f"{API_V1}/auth/login")
def api_events() -> str: return api_url(f"{API_V1}/events")
def api_event(event_id: int) -> str: return api_url(f"{API_V1}/events/{event_id}")
def api_event_status(event_id: int) -> str: return api_url(f"{API_V1}/events/{event_id}/status")
def api_event_registrations(event_id: int) -> str:
    return api_url(f"{API_V1}/events/{event_id}/registrations")
def api_event_broadcasts(event_id: int) -> str:
    return api_url(f"{API_V1}/events/{event_id}/broadcasts")
def api_event_stats(event_id: int) -> str:
    return api_url(f"{API_V1}/events/{event_id}/stats")
def api_scan() -> str: return api_url(f"{API_V1}/scan")
def api_stats() -> str: return api_url(f"{API_V1}/stats")
def api_integration_sync() -> str: return api_url(f"{API_V1}/integration/events/sync")
def api_integration_health() -> str: return api_url(f"{API_V1}/integration/health")

# Пути (без host) — нужны для ApiClient(base_url=...), который сам подставит host.
def path_login() -> str: return f"{API_V1}/auth/login"
def path_events() -> str: return f"{API_V1}/events"
def path_event(event_id: int) -> str: return f"{API_V1}/events/{event_id}"
def path_event_status(event_id: int) -> str: return f"{API_V1}/events/{event_id}/status"
def path_event_registrations(event_id: int) -> str:
    return f"{API_V1}/events/{event_id}/registrations"
def path_event_broadcasts(event_id: int) -> str:
    return f"{API_V1}/events/{event_id}/broadcasts"
def path_event_stats(event_id: int) -> str:
    return f"{API_V1}/events/{event_id}/stats"
def path_scan() -> str: return f"{API_V1}/scan"
def path_stats() -> str: return f"{API_V1}/stats"
def path_healthz() -> str: return f"{API_V1}/healthz"
def path_readyz() -> str: return f"{API_V1}/readyz"
def path_integration_sync() -> str: return f"{API_V1}/integration/events/sync"
def path_integration_health() -> str: return f"{API_V1}/integration/health"
def path_audit_logs() -> str: return f"{API_V1}/audit-logs"
def path_event_slots(event_id: int) -> str: return f"{API_V1}/events/{event_id}/slots"
def path_event_slot(event_id: int, slot_id: int) -> str:
    return f"{API_V1}/events/{event_id}/slots/{slot_id}"
def path_organizers() -> str: return f"{API_V1}/organizers"
def path_organizer(organizer_id: int) -> str: return f"{API_V1}/organizers/{organizer_id}"

# React SPA
def ui_login() -> str: return spa_url("/login")
def ui_events() -> str: return spa_url("/events")
def ui_event(event_id: int) -> str: return spa_url(f"/events/{event_id}")
def ui_event_slots(event_id: int) -> str: return spa_url(f"/events/{event_id}/slots")
def ui_event_scanner(event_id: int) -> str: return spa_url(f"/events/{event_id}/scanner")
def ui_event_wall(event_id: int) -> str: return spa_url(f"/events/{event_id}/wall")
def ui_organizers() -> str: return spa_url("/organizers")
def ui_audit() -> str: return spa_url("/audit")

# Алиасы для постепенной миграции имён в тестах
ui_admin_login = ui_login
ui_admin_events = ui_events
ui_admin_event = ui_event
ui_admin_organizers = ui_organizers
ui_admin_dashboard = ui_events
