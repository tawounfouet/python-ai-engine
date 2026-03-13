"""
Exemple 01 : Découverte des modèles Pydantic de AI Engine avec appels API réels.

Montre comment créer et manipuler les objets métier principaux ET
faire des appels API réels avec les services.
Intègre le système de logging structuré personnalisé.
"""

from ai_engine import (
    Agent,
    AgentConfig,
    AgentMemory,
    AgentRole,
    Conversation,
    Execution,
    ExecutionStep,
    LLMProviderConfig,
    MemoryType,
    Message,
    MessageRole,
    ProviderType,
    StepType,
    ToolDefinition,
    ToolType,
)

# Import des services pour faire les appels réels
from ai_engine.services import AgentService, get_llm_client, LLMRequest

# Import du système de logging personnalisé
from ai_engine.logging import get_logger, configure_logging, LoggingConfig

import asyncio
import os


# Configurer le logging avec un format structuré et couleurs
configure_logging(
    LoggingConfig(
        level="DEBUG",  # Changé pour voir les logs de debug
        json_output=False,  # Format lisible pour la demo
        extra_fields={"component": "ai_engine_demo", "version": "0.1.0"},
    )
)

# Obtenir un logger pour notre exemple
logger = get_logger("examples.quickstart")


async def main():
    logger.debug("🚀 Démarrage de l'exemple quickstart", extra={"function": "main"})

    # ── 1. Provider LLM ─────────────────────────────────────────────────────────

    logger.debug("Création du provider LLM", extra={"step": "provider_creation"})
    provider = LLMProviderConfig(
        name="OpenAI GPT-4o",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key=os.environ.get("OPENAI_API_KEY", "sk-..."),
    )

    # Validation des credentials
    if provider.api_key and len(provider.api_key.get_secret_value()) < 20:
        logger.warning(
            "⚠️  API key semble trop courte",
            extra={"api_key_length": len(provider.api_key.get_secret_value())},
        )
    else:
        logger.debug(
            "✅ API key validée",
            extra={
                "api_key_length": (
                    len(provider.api_key.get_secret_value()) if provider.api_key else 0
                )
            },
        )

    logger.info(
        "Provider LLM configuré",
        extra={
            "provider_name": provider.name,
            "provider_type": str(provider.provider_type),
            "model": provider.default_model,
            "provider_id": provider.id,
            "api_key_masked": (
                provider.api_key.get_secret_value()[:7] + "..."
                if provider.api_key
                else None
            ),
        },
    )
    print(f"Provider : {provider.name} ({provider.provider_type})")
    print(f"  ID auto-généré : {provider.id}")
    print(f"  Modèle par défaut : {provider.default_model}")

    # ── 2. Agent ─────────────────────────────────────────────────────────────────

    logger.debug("Création de l'agent", extra={"step": "agent_creation"})
    agent = Agent(
        name="Assistant Recherche",
        role=AgentRole.RESEARCHER,
        provider_id=provider.id,
        system_prompt="Tu es un chercheur expert en intelligence artificielle.",
        config=AgentConfig(
            temperature=0.7,
            max_tokens_per_run=4096,
            enable_tools=True,
            enable_memory=True,
        ),
    )
    logger.info(
        "Agent créé",
        extra={
            "agent_name": agent.name,
            "agent_role": str(agent.role),
            "provider_id": agent.provider_id,
            "agent_id": agent.id,
            "temperature": agent.config.temperature,
            "max_tokens": agent.config.max_tokens_per_run,
        },
    )
    print(f"\nAgent : {agent.name}")
    print(f"  Rôle : {agent.role}")
    print(f"  Provider : {agent.provider_id}")
    print(f"  Temperature : {agent.config.temperature}")
    print(f"  Tools activés : {agent.config.enable_tools}")

    # ── 3. Conversation & Messages ──────────────────────────────────────────────

    logger.debug(
        "Initialisation de la conversation", extra={"step": "conversation_init"}
    )
    conversation = Conversation(
        agent_id=agent.id,
        title="Recherche sur les LLMs",
    )

    msg_user = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Quels sont les derniers progrès en retrieval-augmented generation ?",
    )

    logger.info(
        "Conversation créée",
        extra={
            "conversation_id": conversation.id,
            "agent_id": conversation.agent_id,
            "title": conversation.title,
            "user_message": msg_user.content,
        },
    )
    print(f"\nConversation : {conversation.title}")
    print(f"  Message user : {msg_user.content}")

    # ── 4. Service LLM pour appel API réel ──────────────────────────────────────

    try:
        # Créer le client LLM à partir du provider
        logger.debug(
            "Création du client LLM",
            extra={"provider_type": str(provider.provider_type)},
        )
        llm_client = get_llm_client(provider)

        logger.info(
            "Début appel API",
            extra={
                "provider_type": str(provider.provider_type),
                "model": provider.default_model,
                "temperature": agent.config.temperature,
                "max_tokens": agent.config.max_tokens_per_run,
            },
        )
        print("\n🔄 Appel API OpenAI en cours...")

        # Préparer la requête
        logger.debug(
            "Préparation de la requête LLM",
            extra={
                "message_count": len(
                    [
                        Message(
                            conversation_id=conversation.id,
                            role=MessageRole.SYSTEM,
                            content=agent.system_prompt,
                        ),
                        msg_user,
                    ]
                ),
                "system_prompt_length": len(agent.system_prompt),
                "user_message_length": len(msg_user.content),
            },
        )
        request = LLMRequest(
            messages=[
                Message(
                    conversation_id=conversation.id,
                    role=MessageRole.SYSTEM,
                    content=agent.system_prompt,
                ),
                msg_user,
            ],
            temperature=agent.config.temperature,
            max_tokens=agent.config.max_tokens_per_run,
        )

        # Appel réel à l'API
        logger.debug(
            "Envoi de la requête à l'API OpenAI",
            extra={"request_id": request.messages[0].id},
        )
        response = await llm_client.acomplete(request)

        msg_assistant = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
        )

        logger.info(
            "Appel API réussi",
            extra={
                "response_id": response.id,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": (
                    response.usage.completion_tokens if response.usage else 0
                ),
                "total_tokens": response.usage.total_tokens if response.usage else 0,
                "response_time_ms": response.response_time_ms,
                "content_length": len(response.content),
            },
        )
        print("✅ Réponse API reçue :")
        print(f"  Tokens utilisés : {response.usage}")
        print(f"  Réponse : {msg_assistant.content[:200]}...")

        # Warning si trop de tokens utilisés
        if response.usage and response.usage.total_tokens > 1000:
            logger.warning(
                "Utilisation élevée de tokens détectée",
                extra={
                    "total_tokens": response.usage.total_tokens,
                    "threshold": 1000,
                    "cost_estimate": response.usage.total_tokens
                    * 0.00002,  # Estimation rough
                },
            )

    except Exception as e:
        logger.error(
            "Erreur lors de l'appel API",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "provider_type": str(provider.provider_type),
            },
            exc_info=True,
        )
        print(f"❌ Erreur lors de l'appel API : {e}")
        # Fallback sur une réponse simulée
        msg_assistant = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Les avancées récentes en RAG incluent ...",
        )

    # ── 5. ToolDefinition ───────────────────────────────────────────────────────

    tool = ToolDefinition(
        key="web_search",
        name="Recherche Web",
        description="Effectue une recherche sur le web",
        tool_type=ToolType.API,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Requête de recherche"},
                "max_results": {
                    "type": "integer",
                    "description": "Nombre max de résultats",
                },
            },
            "required": ["query"],
        },
    )
    print(f"\nTool : {tool.name} (key={tool.key})")
    print(f"  Schema OpenAI : {tool.get_function_schema()}")

    logger.info(
        "Tool défini",
        extra={
            "tool_key": tool.key,
            "tool_name": tool.name,
            "tool_type": str(tool.tool_type),
            "parameters_count": len(tool.parameters_schema.get("properties", {})),
        },
    )

    # ── 6. Mémoire d'agent ──────────────────────────────────────────────────────

    memory = AgentMemory(
        agent_id=agent.id,
        key="user_preferences",
        content='{"langue": "fr", "ton": "formel"}',
        memory_type=MemoryType.LONG_TERM,
    )
    print(f"\nMémoire : {memory.key} ({memory.memory_type})")
    print(f"  Contenu : {memory.content}")

    logger.info(
        "Mémoire d'agent configurée",
        extra={
            "agent_id": memory.agent_id,
            "memory_key": memory.key,
            "memory_type": str(memory.memory_type),
            "content_length": len(memory.content),
        },
    )

    # ── 7. Sérialisation Pydantic ───────────────────────────────────────────────

    # Tous les modèles supportent model_dump() / model_dump_json()
    agent_dict = agent.model_dump()
    print(f"\nAgent en dict — clés : {list(agent_dict.keys())}")

    agent_json = agent.model_dump_json(indent=2)
    print(f"Agent en JSON (extrait) : {agent_json[:120]}...")

    # Reconstruction depuis dict
    agent_copy = Agent.model_validate(agent_dict)
    assert agent_copy.id == agent.id
    print("✅ Reconstruction depuis dict réussie")

    # ── 8. Execution tracking ───────────────────────────────────────────────────

    execution = Execution(
        agent_id=agent.id,
        conversation_id=conversation.id,
    )

    step = ExecutionStep(
        execution_id=execution.id,
        step_type=StepType.LLM_CALL,
        order=1,
        input_data={"prompt": msg_user.content},
        output_data={"response": msg_assistant.content[:100] + "..."},
        tokens_used=response.usage.total_tokens if response.usage else 0,
        duration_ms=int(response.response_time_ms) if response.response_time_ms else 0,
    )

    logger.info(
        "Execution étape créée",
        extra={
            "execution_id": execution.id,
            "step_type": str(step.step_type),
            "step_order": step.order,
            "tokens_used": step.tokens_used,
            "duration_ms": step.duration_ms,
        },
    )
    print(f"\nExecution : {execution.id[:8]}...")
    print(
        f"  Step #{step.order} ({step.step_type}) : {step.tokens_used} tokens, {step.duration_ms}ms"
    )

    print("\n✅ Tous les modèles fonctionnent correctement avec appels API réels !")


# Exécuter la fonction async
if __name__ == "__main__":
    asyncio.run(main())
