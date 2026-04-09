"""
AI Engine Django Adapter — Admin registration.

Enregistre les ORM models ai_engine dans l'admin Django.
Activé automatiquement quand "ai_engine.adapters.django" est dans INSTALLED_APPS.

Pour désactiver :
    AI_ENGINE = {"ADMIN_ENABLED": False}   # dans settings.py
"""

from __future__ import annotations

try:
    from django.contrib import admin
except ImportError as e:
    raise ImportError(
        "Django is required. Install with: pip install ai-engine[django]"
    ) from e

from ai_engine.adapters.django.orm_models import (
    AgentRecord,
    ConversationRecord,
    MessageRecord,
    ProviderRecord,
)


@admin.register(ProviderRecord)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_type", "is_active", "created_at")
    list_filter = ("provider_type", "is_active")
    search_fields = ("name", "id")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("name",)


@admin.register(AgentRecord)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "role", "provider_id", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("name", "slug", "id")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("name",)


@admin.register(ConversationRecord)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "agent_id", "title", "created_at")
    list_filter = ("agent_id",)
    search_fields = ("id", "agent_id", "title")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(MessageRecord)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation_id", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("id", "conversation_id")
    readonly_fields = ("id", "created_at")
    ordering = ("created_at",)
