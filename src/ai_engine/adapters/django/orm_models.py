"""
AI Engine Django Adapter — ORM Models.

Ces models Django définissent le schéma de base de données.
Chaque table stocke :
  - Les colonnes indexées pour les queries fréquentes (id, slug, agent_id, …)
  - Une colonne `data` (JSONField) contenant le domain-model Pydantic sérialisé

Ce pattern "index + JSON blob" permet :
  - Des migrations simples (pas un champ par attribut)
  - Des queries efficaces sur les champs fréquents (filtres, tri)
  - Une évolution indépendante des models Pydantic

Pour générer les migrations :
    python manage.py makemigrations ai_engine
    python manage.py migrate
"""

from __future__ import annotations

from django.db import models


class ProviderRecord(models.Model):
    """Stockage d'un LLMProviderConfig."""

    id = models.CharField(max_length=36, primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    provider_type = models.CharField(max_length=50, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai_engine"
        db_table = "ai_engine_providers"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.provider_type})"


class AgentRecord(models.Model):
    """Stockage d'un Agent."""

    id = models.CharField(max_length=36, primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    provider_id = models.CharField(max_length=36, db_index=True)
    role = models.CharField(max_length=50, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai_engine"
        db_table = "ai_engine_agents"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class ConversationRecord(models.Model):
    """Stockage d'une Conversation."""

    id = models.CharField(max_length=36, primary_key=True)
    agent_id = models.CharField(max_length=36, db_index=True)
    title = models.CharField(max_length=500, blank=True, default="")
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai_engine"
        db_table = "ai_engine_conversations"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Conversation {self.id[:8]} — agent {self.agent_id[:8]}"


class MessageRecord(models.Model):
    """Stockage d'un Message."""

    id = models.CharField(max_length=36, primary_key=True)
    conversation_id = models.CharField(max_length=36, db_index=True)
    role = models.CharField(max_length=20, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai_engine"
        db_table = "ai_engine_messages"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"[{self.role}] {self.id[:8]} in conv {self.conversation_id[:8]}"
