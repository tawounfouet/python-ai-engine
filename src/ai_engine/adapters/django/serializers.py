"""
AI Engine Django Adapter — DRF Serializers.

Convention :
  <Entity>Serializer        — lecture (GET) : champs complets, pas de api_key
  <Entity>CreateSerializer  — écriture (POST) : champs requis pour la création
  <Entity>UpdateSerializer  — mise à jour partielle (PATCH)
"""

from __future__ import annotations

try:
    from rest_framework import serializers
except ImportError as e:
    raise ImportError(
        "DRF serializers require djangorestframework. "
        "Install with: pip install ai-engine[django]"
    ) from e


# ── Provider ──────────────────────────────────────────────────────────────────


class ProviderSerializer(serializers.Serializer):
    """Lecture d'un provider (api_key non exposée)."""

    id = serializers.CharField(read_only=True)
    name = serializers.CharField()
    provider_type = serializers.CharField()
    default_model = serializers.CharField()
    api_base_url = serializers.CharField(allow_null=True, required=False)
    has_api_key = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_has_api_key(self, obj: object) -> bool:
        api_key = getattr(obj, "api_key", None)
        if api_key is None:
            return False
        # Pydantic SecretStr or plain string
        try:
            return bool(api_key.get_secret_value())
        except AttributeError:
            return bool(api_key)


class ProviderCreateSerializer(serializers.Serializer):
    """Création d'un provider."""

    name = serializers.CharField(max_length=255)
    provider_type = serializers.CharField(max_length=50)
    default_model = serializers.CharField(max_length=255)
    api_key = serializers.CharField(
        required=False,
        allow_null=True,
        write_only=True,
        style={"input_type": "password"},
    )
    api_base_url = serializers.CharField(required=False, allow_null=True)
    is_default = serializers.BooleanField(default=False)
    is_active = serializers.BooleanField(default=True)


class ProviderUpdateSerializer(serializers.Serializer):
    """Mise à jour partielle d'un provider."""

    name = serializers.CharField(max_length=255, required=False)
    default_model = serializers.CharField(max_length=255, required=False)
    api_key = serializers.CharField(
        required=False,
        allow_null=True,
        write_only=True,
        style={"input_type": "password"},
    )
    api_base_url = serializers.CharField(required=False, allow_null=True)
    is_default = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


# ── Agent ─────────────────────────────────────────────────────────────────────


class AgentSerializer(serializers.Serializer):
    """Lecture d'un agent."""

    id = serializers.CharField(read_only=True)
    name = serializers.CharField()
    slug = serializers.CharField()
    description = serializers.CharField()
    role = serializers.CharField()
    provider_id = serializers.CharField()
    system_prompt = serializers.CharField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AgentCreateSerializer(serializers.Serializer):
    """Création d'un agent."""

    name = serializers.CharField(max_length=255)
    provider_id = serializers.CharField()
    system_prompt = serializers.CharField(default="")
    role = serializers.CharField(default="assistant")
    slug = serializers.SlugField(required=False, allow_null=True)
    description = serializers.CharField(required=False, default="")
    is_active = serializers.BooleanField(default=True)


class AgentUpdateSerializer(serializers.Serializer):
    """Mise à jour partielle d'un agent."""

    name = serializers.CharField(max_length=255, required=False)
    system_prompt = serializers.CharField(required=False)
    description = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False)


# ── Conversation ──────────────────────────────────────────────────────────────


class ConversationSerializer(serializers.Serializer):
    """Lecture d'une conversation."""

    id = serializers.CharField(read_only=True)
    agent_id = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    message_count = serializers.IntegerField(read_only=True, default=0)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ConversationCreateSerializer(serializers.Serializer):
    """Démarrage d'une conversation."""

    agent_id = serializers.CharField()
    title = serializers.CharField(required=False, default="")


# ── Message ───────────────────────────────────────────────────────────────────


class MessageSerializer(serializers.Serializer):
    """Lecture d'un message."""

    id = serializers.CharField(read_only=True)
    conversation_id = serializers.CharField()
    role = serializers.CharField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)


# ── Chat ──────────────────────────────────────────────────────────────────────


class ChatRequestSerializer(serializers.Serializer):
    """Requête de chat."""

    agent_id = serializers.CharField()
    message = serializers.CharField(min_length=1)
    conversation_id = serializers.CharField(required=False, allow_null=True)


class ChatResponseSerializer(serializers.Serializer):
    """Réponse de chat."""

    content = serializers.CharField()
    conversation_id = serializers.CharField()
    model = serializers.CharField(allow_null=True, required=False)
    agent_id = serializers.CharField()
