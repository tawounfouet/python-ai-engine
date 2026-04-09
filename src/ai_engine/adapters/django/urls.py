"""
AI Engine Django Adapter — URL configuration.

Incluez dans votre urls.py :

    from ai_engine.adapters.django.urls import urlpatterns as ai_engine_urls

    urlpatterns = [
        ...
        path("api/ai/", include((ai_engine_urls, "ai_engine"))),
    ]

Ou avec un préfixe personnalisé :

    urlpatterns += [
        path("api/v1/", include((ai_engine_urls, "ai_engine"))),
    ]

Routes disponibles :
  GET/POST   providers/
  GET/PATCH/DELETE providers/<provider_id>/
  GET/POST   agents/
  GET/PATCH/DELETE agents/<agent_id>/
  GET/POST   conversations/
  GET/DELETE conversations/<conv_id>/
  GET        conversations/<conv_id>/messages/
  POST       chat/
"""

from __future__ import annotations

try:
    from django.urls import path
except ImportError as e:
    raise ImportError(
        "Django is required. Install with: pip install ai-engine[django]"
    ) from e

from ai_engine.adapters.django.views import (
    AgentDetailView,
    AgentListCreateView,
    ChatView,
    ConversationDetailView,
    ConversationListCreateView,
    ConversationMessageListView,
    ProviderDetailView,
    ProviderListCreateView,
)

urlpatterns = [
    # Providers
    path(
        "providers/", ProviderListCreateView.as_view(), name="ai_engine-provider-list"
    ),
    path(
        "providers/<str:provider_id>/",
        ProviderDetailView.as_view(),
        name="ai_engine-provider-detail",
    ),
    # Agents
    path("agents/", AgentListCreateView.as_view(), name="ai_engine-agent-list"),
    path(
        "agents/<str:agent_id>/",
        AgentDetailView.as_view(),
        name="ai_engine-agent-detail",
    ),
    # Conversations
    path(
        "conversations/",
        ConversationListCreateView.as_view(),
        name="ai_engine-conversation-list",
    ),
    path(
        "conversations/<str:conv_id>/",
        ConversationDetailView.as_view(),
        name="ai_engine-conversation-detail",
    ),
    path(
        "conversations/<str:conv_id>/messages/",
        ConversationMessageListView.as_view(),
        name="ai_engine-conversation-messages",
    ),
    # Chat
    path("chat/", ChatView.as_view(), name="ai_engine-chat"),
]
