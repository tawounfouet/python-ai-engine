"""
AI Engine Django Adapter — AppConfig.
"""

from __future__ import annotations

from django.apps import AppConfig


class AiEngineConfig(AppConfig):
    """
    Django AppConfig pour l'adaptateur ai_engine.

    Déclarez dans settings.py :
        INSTALLED_APPS = [
            ...
            "ai_engine.adapters.django",
        ]

    Configuration optionnelle dans settings.py :
        AI_ENGINE = {
            "EVENT_BUS_ENABLED": True,     # Active le bridge signals → EventBus
            "ADMIN_ENABLED":     True,     # Enregistre les models dans l'admin Django
        }
    """

    name = "ai_engine.adapters.django"
    label = "ai_engine"
    verbose_name = "AI Engine"

    def ready(self) -> None:
        """
        Appelé quand Django a fini de charger tous les apps.
        Connecte les signals Django → EventBus si activé.
        """
        from django.conf import settings as django_settings

        cfg = getattr(django_settings, "AI_ENGINE", {})

        if cfg.get("EVENT_BUS_ENABLED", True):
            # Import déclenche la connexion des receivers
            from ai_engine.adapters.django import signals  # noqa: F401
