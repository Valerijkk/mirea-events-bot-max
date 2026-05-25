"""Фабрика пользователей MAX. Применяется в потенциальных расширениях."""
from __future__ import annotations

import factory
from faker import Faker

_fake_ru = Faker("ru_RU")


class UserFactory(factory.DictFactory):
    max_user_id = factory.Sequence(lambda n: 2_000_000 + n)
    full_name = factory.LazyFunction(lambda: _fake_ru.name())
    phone = factory.LazyFunction(lambda: _fake_ru.phone_number())
