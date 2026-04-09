"""
AI Engine Django Adapter — DRF Views.

Expose les ressources ai_engine via des APIViews DRF.
Montez ces vues dans urls.py via :

    from ai_engine.adapters.django.urls import urlpatterns as ai_urls
    urlpatterns += ai_urls
"""

from __future__ import annotations

try:
    from rest_framework import status
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.views import APIView
except ImportError as e:
    raise ImportError(
        "DRF views require djangorestframework. "
        "Install with: pip install ai-engine[django]"
    ) from e

from ai_engine.adapters.django.serializers import (
    AgentCreateSerializer,
    AgentSerializer,
    AgentUpdateSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer,
    ConversationCreateSerializer,
    ConversationSerializer,
    MessageSerializer,
    ProviderCreateSerializer,
    ProviderSerializer,
    ProviderUpdateSerializer,
)
from ai_engine.adapters.django.storage import DjangoORMStorage
from ai_engine.exceptions import AgentNotFoundError, ProviderNotFoundError
from ai_engine.services.agent import AgentService


def _get_storage() -> DjangoORMStorage:
    """Retourne une instance DjangoORMStorage."""
    return DjangoORMStorage()


def _get_svc() -> AgentService:
    return AgentService(_get_storage())


def _paginate(items: list, request: Request) -> dict:
    limit = int(request.query_params.get("limit", 20))
    offset = int(request.query_params.get("offset", 0))
    page = items[offset : offset + limit]
    return {"total": len(items), "limit": limit, "offset": offset, "items": page}


# ── Providers ─────────────────────────────────────────────────────────────────


class ProviderListCreateView(APIView):
    """GET /providers  — liste · POST /providers — créer."""

    def get(self, request: Request) -> Response:
        storage = _get_storage()
        providers = storage.list_providers()
        serializer = ProviderSerializer(providers, many=True)
        page = _paginate(serializer.data, request)
        return Response(page)

    def post(self, request: Request) -> Response:
        serializer = ProviderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from ai_engine.models.provider import LLMProviderConfig
        from ai_engine.types import ProviderType

        try:
            pt = ProviderType(data["provider_type"])
        except ValueError:
            return Response(
                {"detail": f"Unknown provider_type '{data['provider_type']}'."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        provider = LLMProviderConfig(
            name=data["name"],
            provider_type=pt,
            default_model=data["default_model"],
            api_key=data.get("api_key"),
            api_base_url=data.get("api_base_url"),
            is_default=data.get("is_default", False),
            is_active=data.get("is_active", True),
        )
        storage = _get_storage()
        saved = storage.save_provider(provider)
        return Response(ProviderSerializer(saved).data, status=status.HTTP_201_CREATED)


class ProviderDetailView(APIView):
    """GET/PATCH/DELETE /providers/{id}."""

    def _get_or_404(self, provider_id: str):
        storage = _get_storage()
        provider = storage.get_provider(provider_id)
        if not provider:
            from rest_framework.exceptions import NotFound

            raise NotFound(f"Provider '{provider_id}' not found.")
        return storage, provider

    def get(self, request: Request, provider_id: str) -> Response:
        _, provider = self._get_or_404(provider_id)
        return Response(ProviderSerializer(provider).data)

    def patch(self, request: Request, provider_id: str) -> Response:
        from datetime import UTC, datetime

        serializer = ProviderUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        storage, provider = self._get_or_404(provider_id)
        for field, value in data.items():
            if value is not None:
                setattr(provider, field, value)
        provider.updated_at = datetime.now(UTC)
        storage.save_provider(provider)
        return Response(ProviderSerializer(provider).data)

    def delete(self, request: Request, provider_id: str) -> Response:
        storage, _ = self._get_or_404(provider_id)
        storage.delete_provider(provider_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Agents ────────────────────────────────────────────────────────────────────


class AgentListCreateView(APIView):
    """GET /agents — liste · POST /agents — créer."""

    def get(self, request: Request) -> Response:
        storage = _get_storage()
        active_only = request.query_params.get("active_only", "").lower() == "true"
        agents = storage.list_agents(is_active=True if active_only else None)
        serializer = AgentSerializer(agents, many=True)
        page = _paginate(serializer.data, request)
        return Response(page)

    def post(self, request: Request) -> Response:
        serializer = AgentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from ai_engine.types import AgentRole

        try:
            role = AgentRole(data.get("role", "assistant"))
        except ValueError:
            valid = [r.value for r in AgentRole]
            return Response(
                {"detail": f"Unknown role '{data['role']}'. Valid: {valid}"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        svc = _get_svc()
        try:
            agent = svc.create_agent(
                name=data["name"],
                provider_id=data["provider_id"],
                system_prompt=data.get("system_prompt", ""),
                role=role,
                slug=data.get("slug"),
                description=data.get("description", ""),
                is_active=data.get("is_active", True),
            )
        except ProviderNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(AgentSerializer(agent).data, status=status.HTTP_201_CREATED)


class AgentDetailView(APIView):
    """GET/PATCH/DELETE /agents/{id}."""

    def _get_or_404(self, agent_id: str):
        storage = _get_storage()
        agent = storage.get_agent(agent_id) or storage.get_agent_by_slug(agent_id)
        if not agent:
            from rest_framework.exceptions import NotFound

            raise NotFound(f"Agent '{agent_id}' not found.")
        return storage, agent

    def get(self, request: Request, agent_id: str) -> Response:
        _, agent = self._get_or_404(agent_id)
        return Response(AgentSerializer(agent).data)

    def patch(self, request: Request, agent_id: str) -> Response:
        from datetime import UTC, datetime

        serializer = AgentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        storage, agent = self._get_or_404(agent_id)
        for field, value in data.items():
            setattr(agent, field, value)
        agent.updated_at = datetime.now(UTC)
        storage.save_agent(agent)
        return Response(AgentSerializer(agent).data)

    def delete(self, request: Request, agent_id: str) -> Response:
        storage, _ = self._get_or_404(agent_id)
        storage.delete_agent(_.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Conversations ─────────────────────────────────────────────────────────────


class ConversationListCreateView(APIView):
    """GET /conversations — liste · POST /conversations — créer."""

    def get(self, request: Request) -> Response:
        storage = _get_storage()
        agent_id = request.query_params.get("agent_id")
        conversations = storage.list_conversations(agent_id=agent_id)
        serializer = ConversationSerializer(conversations, many=True)
        page = _paginate(serializer.data, request)
        return Response(page)

    def post(self, request: Request) -> Response:
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        storage = _get_storage()
        agent = storage.get_agent(data["agent_id"]) or storage.get_agent_by_slug(
            data["agent_id"]
        )
        if not agent:
            return Response(
                {"detail": f"Agent '{data['agent_id']}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from ai_engine.models.conversation import Conversation

        conv = Conversation(
            agent_id=agent.id,
            title=data.get("title", ""),
        )
        saved = storage.save_conversation(conv)
        return Response(
            ConversationSerializer(saved).data, status=status.HTTP_201_CREATED
        )


class ConversationDetailView(APIView):
    """GET/DELETE /conversations/{id}."""

    def _get_or_404(self, conv_id: str):
        storage = _get_storage()
        conv = storage.get_conversation(conv_id)
        if not conv:
            from rest_framework.exceptions import NotFound

            raise NotFound(f"Conversation '{conv_id}' not found.")
        return storage, conv

    def get(self, request: Request, conv_id: str) -> Response:
        _, conv = self._get_or_404(conv_id)
        return Response(ConversationSerializer(conv).data)

    def delete(self, request: Request, conv_id: str) -> Response:
        storage, _ = self._get_or_404(conv_id)
        storage.delete_conversation(conv_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationMessageListView(APIView):
    """GET /conversations/{id}/messages — historique."""

    def get(self, request: Request, conv_id: str) -> Response:
        storage = _get_storage()
        if not storage.get_conversation(conv_id):
            from rest_framework.exceptions import NotFound

            raise NotFound(f"Conversation '{conv_id}' not found.")

        limit = request.query_params.get("limit")
        offset = int(request.query_params.get("offset", 0))
        messages = storage.get_messages(
            conv_id,
            limit=int(limit) if limit else None,
            offset=offset,
        )
        serializer = MessageSerializer(messages, many=True)
        return Response(
            {
                "total": storage.count_messages(conv_id),
                "limit": int(limit) if limit else None,
                "offset": offset,
                "items": serializer.data,
            }
        )


# ── Chat ──────────────────────────────────────────────────────────────────────


class ChatView(APIView):
    """POST /chat — envoyer un message à un agent."""

    def post(self, request: Request) -> Response:
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data["message"].strip():
            return Response(
                {"detail": "message cannot be empty."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        svc = _get_svc()
        try:
            response, conversation = svc.chat(
                agent_id=data["agent_id"],
                message=data["message"],
                conversation_id=data.get("conversation_id"),
            )
        except AgentNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            ChatResponseSerializer(
                {
                    "content": response.content,
                    "conversation_id": conversation.id,
                    "model": getattr(response, "model", None),
                    "agent_id": data["agent_id"],
                }
            ).data
        )
