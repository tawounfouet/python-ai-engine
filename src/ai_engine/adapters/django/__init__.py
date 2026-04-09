"""
AI Engine — Django Adapter (Phase 5.3).

Intègre ai_engine dans un projet Django existant en fournissant :
  - DjangoORMStorage  : StorageBackend qui persiste via l'ORM Django
  - AiEngineConfig    : AppConfig Django à déclarer dans INSTALLED_APPS
  - Serializers DRF   : lecture/écriture des ressources ai_engine
  - ViewSets DRF      : API REST montable via un router DRF
  - urls              : urlpatterns prêts à inclure dans urls.py
  - signals           : bridge Django signals → EventBus ai_engine
  - admin             : enregistrement dans l'admin Django

Usage minimal :

    # settings.py
    INSTALLED_APPS = [
        ...
        "ai_engine.adapters.django",
    ]

    # urls.py
    from ai_engine.adapters.django.urls import urlpatterns as ai_engine_urls
    urlpatterns += ai_engine_urls

    # views.py / services.py
    from ai_engine.adapters.django import DjangoORMStorage
    from ai_engine.services import AgentService

    storage = DjangoORMStorage()
    svc = AgentService(storage)
"""

from __future__ import annotations

try:
    import django  # noqa: F401
except ImportError as e:
    raise ImportError(
        "Django adapter requires Django. " "Install with: pip install ai-engine[django]"
    ) from e

from ai_engine.adapters.django.apps import AiEngineConfig
from ai_engine.adapters.django.storage import DjangoORMStorage

__all__ = ["AiEngineConfig", "DjangoORMStorage"]

# Required for Django to discover this as an AppConfig
default_app_config = "ai_engine.adapters.django.apps.AiEngineConfig"
