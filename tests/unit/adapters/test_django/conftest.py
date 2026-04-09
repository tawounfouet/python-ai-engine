"""
Conftest for Django adapter tests.

Configures a minimal in-memory Django setup before any test runs.
Uses pytest-django's --ds / DJANGO_SETTINGS_MODULE approach but
with inline settings to avoid needing a real settings file.
"""

from __future__ import annotations

import django
from django.conf import settings


def pytest_configure(config):
    """Configure minimal Django settings for adapter tests."""
    if not settings.configured:
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "ai_engine.adapters.django",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            AI_ENGINE={"EVENT_BUS_ENABLED": False},  # Disable signals in tests
        )
        django.setup()


# Override pytest-django's database setup to create tables without migrations
import pytest  # noqa: E402


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    """Create ORM tables directly — no migrations directory needed."""
    from django.db import connection
    from ai_engine.adapters.django.orm_models import (
        AgentRecord,
        ConversationRecord,
        MessageRecord,
        ProviderRecord,
    )

    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in (
                ProviderRecord,
                AgentRecord,
                ConversationRecord,
                MessageRecord,
            ):
                editor.create_model(model)
