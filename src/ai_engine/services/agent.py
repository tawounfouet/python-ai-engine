"""
Agent Service Layer.

Service de haut niveau pour gérer les agents AI:
- Création et configuration des agents
- Exécution de tâches et conversations
- Gestion de la mémoire et du contexte
- Orchestration des tools et providers

Usage:
    storage = SQLiteStorage("agents.db")
    agent_service = AgentService(storage)

    agent = agent_service.create_agent(
        name="Assistant",
        provider_id="openai-gpt4",
        system_prompt="You are a helpful assistant",
    )

    response = agent_service.chat(agent.id, "Hello!")
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ai_engine.exceptions import AgentError, AgentNotFoundError, ProviderNotFoundError
from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.message import Message
from ai_engine.services.llm import LLMRequest, get_llm_client
from ai_engine.storage.base import StorageBackend
from ai_engine.types import AgentRole, MessageRole

if TYPE_CHECKING:
    from ai_engine.tools.registry import ToolRegistry


class AgentService:
    """Service principal pour la gestion des agents."""

    def __init__(
        self,
        storage: StorageBackend,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        from ai_engine.tools.executor import ToolExecutor as _ToolExecutor
        from ai_engine.tools.registry import ToolRegistry as _ToolRegistry

        self.storage = storage
        self.tool_registry = tool_registry or _ToolRegistry()
        self.tool_executor = _ToolExecutor(self.tool_registry)

    def create_agent(
        self,
        name: str,
        provider_id: str,
        system_prompt: str = "",
        role: AgentRole = AgentRole.ASSISTANT,
        config: AgentConfig | None = None,
        **kwargs: Any,
    ) -> Agent:
        """
        Crée un nouvel agent.

        Args:
            name: Nom de l'agent
            provider_id: ID du provider LLM à utiliser
            system_prompt: Prompt système
            role: Rôle de l'agent
            config: Configuration avancée
            **kwargs: Autres paramètres pour Agent

        Returns:
            L'agent créé

        Raises:
            ProviderNotFoundError: Si le provider n'existe pas
        """
        # Vérifier que le provider existe
        provider = self.storage.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError(provider_id)

        # Configuration par défaut
        if config is None:
            config = AgentConfig()

        # Créer l'agent
        _slug_raw = kwargs.pop("slug", None)
        slug = _slug_raw if _slug_raw is not None else name.lower().replace(" ", "-")
        agent = Agent(
            name=name,
            provider_id=provider_id,
            system_prompt=system_prompt,
            role=role,
            config=config,
            slug=slug,
            **kwargs,
        )

        # Sauvegarder
        return self.storage.save_agent(agent)

    def get_agent(self, agent_id: str) -> Agent:
        """
        Récupère un agent par ID.

        Args:
            agent_id: ID de l'agent

        Returns:
            L'agent

        Raises:
            AgentNotFoundError: Si l'agent n'existe pas
        """
        agent = self.storage.get_agent(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)
        return agent

    def update_agent(self, agent_id: str, **updates: Any) -> Agent:
        """
        Met à jour un agent.

        Args:
            agent_id: ID de l'agent
            **updates: Champs à mettre à jour

        Returns:
            L'agent mis à jour
        """
        agent = self.get_agent(agent_id)

        # Appliquer les mises à jour
        for field, value in updates.items():
            if hasattr(agent, field):
                setattr(agent, field, value)

        agent.updated_at = datetime.now(UTC)
        return self.storage.save_agent(agent)

    def delete_agent(self, agent_id: str) -> bool:
        """
        Supprime un agent.

        Args:
            agent_id: ID de l'agent

        Returns:
            True si supprimé avec succès
        """
        return self.storage.delete_agent(agent_id)

    def list_agents(
        self,
        owner_id: str | None = None,
        role: AgentRole | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]:
        """
        Liste les agents selon des critères.

        Args:
            owner_id: Filtrer par propriétaire
            role: Filtrer par rôle
            is_active: Filtrer par statut actif

        Returns:
            Liste des agents
        """
        return self.storage.list_agents(
            owner_id=owner_id,
            role=role,
            is_active=is_active,
        )

    def create_conversation(
        self,
        agent_id: str,
        title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        """
        Crée une nouvelle conversation pour un agent.

        Args:
            agent_id: ID de l'agent
            title: Titre de la conversation
            metadata: Métadonnées

        Returns:
            La conversation créée
        """
        # Vérifier que l'agent existe
        agent = self.get_agent(agent_id)

        conversation = Conversation(
            agent_id=agent_id,
            title=title or f"Conversation with {agent.name}",
            metadata=metadata or {},
        )

        return self.storage.save_conversation(conversation)

    def chat(
        self,
        agent_id: str,
        message: str,
        conversation_id: str | None = None,
        **llm_options: Any,
    ) -> tuple[Message, Conversation]:
        """
        Envoie un message à un agent et retourne sa réponse.

        Si l'agent a des tools enregistrés et que le LLM demande des tool_calls,
        la boucle tool-calling est exécutée automatiquement.

        Args:
            agent_id: ID de l'agent
            message: Message utilisateur
            conversation_id: ID de la conversation (créée si None)
            **llm_options: Options pour le LLM

        Returns:
            Tuple (réponse de l'agent, conversation)
        """
        # Récupérer l'agent et son provider
        agent = self.get_agent(agent_id)
        provider = self.storage.get_provider(agent.provider_id)
        if not provider:
            raise ProviderNotFoundError(agent.provider_id)

        # Créer ou récupérer la conversation
        if conversation_id:
            conversation = self.storage.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = self.create_conversation(agent_id)

        # Créer le message utilisateur
        user_message = Message(
            conversation_id=conversation.id,
            content=message,
            role=MessageRole.USER,
        )
        user_message = self.storage.save_message(user_message)

        # Préparer le contexte de la conversation
        messages = self._build_conversation_context(agent, conversation.id)
        messages.append(user_message)

        # Appeler le LLM
        llm_client = get_llm_client(provider)

        try:
            # Si des tools sont enregistrés et que l'agent les supporte → boucle tool-calling
            has_tools = agent.config.enable_tools and len(self.tool_registry) > 0

            if has_tools:
                llm_response = self.tool_executor.run_tool_loop(
                    client=llm_client,
                    messages=messages,
                    max_iterations=agent.config.max_iterations,
                    conversation_id=conversation.id,
                )
            else:
                llm_request = LLMRequest(
                    messages=messages,
                    temperature=llm_options.get(
                        "temperature", agent.config.temperature
                    ),
                    max_tokens=llm_options.get(
                        "max_tokens", agent.config.max_tokens_per_response
                    ),
                )
                llm_response = llm_client.complete(llm_request)

            # Créer le message de réponse
            assistant_message = Message(
                conversation_id=conversation.id,
                content=llm_response.content,
                role=MessageRole.ASSISTANT,
                metadata={
                    "llm_response": llm_response.model_dump(),
                    "agent_id": agent_id,
                },
            )
            assistant_message = self.storage.save_message(assistant_message)

            # Mettre à jour la conversation
            conversation.updated_at = datetime.now(UTC)
            conversation = self.storage.save_conversation(conversation)

            return assistant_message, conversation

        except Exception as e:
            raise AgentError(f"Error during agent conversation: {e}") from e

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        """
        Récupère l'historique d'une conversation.

        Args:
            conversation_id: ID de la conversation
            limit: Nombre maximum de messages
            offset: Offset pour la pagination

        Returns:
            Liste des messages
        """
        return self.storage.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )

    def _build_conversation_context(
        self,
        agent: Agent,
        conversation_id: str,
        max_messages: int = 50,
    ) -> list[Message]:
        """
        Construit le contexte de conversation pour le LLM.

        Args:
            agent: L'agent
            conversation_id: ID de la conversation
            max_messages: Nombre max de messages à inclure

        Returns:
            Liste des messages contextuels
        """
        messages = []

        # Ajouter le system prompt si défini
        if agent.system_prompt:
            system_message = Message(
                content=agent.system_prompt,
                role=MessageRole.SYSTEM,
                conversation_id=conversation_id,
            )
            messages.append(system_message)

        # Récupérer l'historique récent
        history = self.storage.get_messages(
            conversation_id=conversation_id,
            limit=max_messages,
        )

        messages.extend(history)
        return messages

    def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """
        Récupère les statistiques d'un agent.

        Args:
            agent_id: ID de l'agent

        Returns:
            Dictionnaire avec les statistiques
        """
        # Compter les conversations
        conversations = self.storage.list_conversations(agent_id=agent_id)
        conversation_count = len(conversations)

        # Compter les messages
        total_messages = 0
        for conv in conversations:
            messages = self.storage.get_messages(conversation_id=conv.id)
            total_messages += len(messages)

        return {
            "conversation_count": conversation_count,
            "total_messages": total_messages,
            "agent_id": agent_id,
        }
