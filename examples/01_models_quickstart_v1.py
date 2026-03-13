"""
Exemple 01 : Découverte des modèles Pydantic de AI Engine.

Montre comment créer et manipuler les objets métier principaux :
  - LLMProviderConfig (configuration d'un provider LLM)
  - Agent (agent AI configuré)
  - Conversation, Message
  - ToolDefinition
  - AgentMemory, KnowledgeSource, Execution

Aucune clé API nécessaire — tout fonctionne en local.
"""

import os

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

# ── 1. Provider LLM ─────────────────────────────────────────────────────────

provider = LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY", "sk-..."),  # pas utilisé ici
)
print(f"Provider : {provider.name} ({provider.provider_type})")
print(f"  ID auto-généré : {provider.id}")
print(f"  Modèle par défaut : {provider.default_model}")

# ── 2. Agent ─────────────────────────────────────────────────────────────────

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
print(f"\nAgent : {agent.name}")
print(f"  Rôle : {agent.role}")
print(f"  Provider : {agent.provider_id}")
print(f"  Temperature : {agent.config.temperature}")
print(f"  Tools activés : {agent.config.enable_tools}")

# ── 3. Conversation & Messages ──────────────────────────────────────────────

conversation = Conversation(
    agent_id=agent.id,
    title="Recherche sur les LLMs",
)

msg_user = Message(
    conversation_id=conversation.id,
    role=MessageRole.USER,
    content="Quels sont les derniers progrès en retrieval-augmented generation ?",
)

msg_assistant = Message(
    conversation_id=conversation.id,
    role=MessageRole.ASSISTANT,
    content="Les avancées récentes en RAG incluent ...",
)

print(f"\nConversation : {conversation.title}")
print(f"  Message user : {msg_user.content[:60]}...")
print(f"  Message assistant : {msg_assistant.content[:60]}...")

# ── 4. ToolDefinition ───────────────────────────────────────────────────────

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

# ── 5. Mémoire d'agent ──────────────────────────────────────────────────────

memory = AgentMemory(
    agent_id=agent.id,
    key="user_preferences",
    content='{"langue": "fr", "ton": "formel"}',
    memory_type=MemoryType.LONG_TERM,
)
print(f"\nMémoire : {memory.key} ({memory.memory_type})")
print(f"  Contenu : {memory.content}")

# ── 6. Sérialisation Pydantic ───────────────────────────────────────────────

# Tous les modèles supportent model_dump() / model_dump_json()
agent_dict = agent.model_dump()
print(f"\nAgent en dict — clés : {list(agent_dict.keys())}")

agent_json = agent.model_dump_json(indent=2)
print(f"Agent en JSON (extrait) : {agent_json[:120]}...")

# Reconstruction depuis dict
agent_copy = Agent.model_validate(agent_dict)
assert agent_copy.id == agent.id
print("✅ Reconstruction depuis dict réussie")

# ── 7. Execution tracking ───────────────────────────────────────────────────

execution = Execution(
    agent_id=agent.id,
    conversation_id=conversation.id,
)

step = ExecutionStep(
    execution_id=execution.id,
    step_type=StepType.LLM_CALL,
    order=1,
    input_data={"prompt": "Analyse les tendances IA..."},
    output_data={"response": "Les tendances principales sont..."},
    tokens_used=1500,
    duration_ms=820,
)
print(f"\nExecution : {execution.id[:8]}...")
print(
    f"  Step #{step.order} ({step.step_type}) : {step.tokens_used} tokens, {step.duration_ms}ms"
)

print("\n✅ Tous les modèles fonctionnent correctement !")
