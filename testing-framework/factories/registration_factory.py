"""Фабрика payload-ов регистрации. Снаружи через API не создаётся (это делает MAX-бот),
живёт здесь как заготовка для будущей test-only ручки."""
from __future__ import annotations

import factory


class RegistrationFactory(factory.DictFactory):
    status = "confirmed"
    event_id = 1
