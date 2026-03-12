# 06 — Flux de données et interactions entre couches

Ce document décrit les **flux concrets** qui traversent les couches de l'architecture,
du point d'entrée utilisateur jusqu'au stockage et aux APIs externes.

---

## 6.1 Flux : création d'un agent

```
[Code utilisateur]
    │
    ▼
AgentService.create_agent(
    name="Research Assistant",
    provider_id="<uuid>",
    system_prompt="Tu es...",
)
    │
    ├─► storage.get_provider("<uuid>")
    │       │
    │       └─► [StorageBackend] → retourne LLMProviderConfig | None
    │                               ← si None → lève ProviderNotFoundError
    │
    ├─► Instanciation Agent(
    │       id=uuid4(),
    │       name="Research Assistant",
    │       slug="research-assistant",  ← généré depuis name
    │       provider_id="<uuid>",
    │       system_prompt="Tu es...",
    │       config=AgentConfig(),       ← valeurs par défaut
    │       created_at=datetime.now(UTC),
    │   )
    │
    └─► storage.save_agent(agent)
            │
            └─► [StorageBackend] → persiste + retourne Agent
```

---

## 6.2 Flux : session de chat complète

```
[Code utilisateur]
    │
    ▼
AgentService.chat(
    agent_id="<uuid-agent>",
    message="Quelle est la capitale de la France ?",
    conversation_id=None,
)
    │
    ├─► storage.get_agent("<uuid-agent>")
    │       └─► Agent | lève AgentNotFoundError
    │
    ├─► storage.get_provider(agent.provider_id)
    │       └─► LLMProviderConfig | lève ProviderNotFoundError
    │
    ├─► [conversation_id est None]
    │   └─► Instanciation Conversation(agent_id=...)
    │   └─► storage.save_conversation(conv)
    │
    ├─► [Persister message utilisateur]
    │   Message(
    │       conversation_id=conv.id,
    │       role=MessageRole.USER,
    │       content="Quelle est la capitale...",
    │   )
    │   └─► storage.save_message(user_message)
    │
    ├─► [Charger l'historique]
    │   └─► storage.get_messages(conv.id, limit=50)
    │
    ├─► [Construire LLMRequest]
    │   messages = [
    │       Message(role=SYSTEM, content=agent.system_prompt),
    │       ...historique...,
    │       Message(role=USER, content="Quelle est la capitale..."),
    │   ]
    │   LLMRequest(messages=messages, model=..., temperature=...)
    │
    ├─► get_llm_client(provider) → LLMClient
    │       └─► Factory → OpenAIClient(provider)
    │
    ├─► client.complete(request) → LLMResponse
    │       │
    │       └─► [APPEL API EXTERNE]
    │               OpenAI / Anthropic / Ollama...
    │               ← LLMResponse(content="Paris est la capitale...")
    │
    ├─► [Persister message assistant]
    │   Message(
    │       conversation_id=conv.id,
    │       role=MessageRole.ASSISTANT,
    │       content="Paris est la capitale...",
    │       token_usage=TokenUsage(prompt=50, completion=20, total=70),
    │   )
    │   └─► storage.save_message(assistant_message)
    │
    ├─► [Mettre à jour la conversation]
    │   conversation.message_count += 2
    │   conversation.total_tokens += 70
    │   conversation.last_message_at = datetime.now(UTC)
    │   └─► storage.save_conversation(conversation)
    │
    └─► retourne (response_text, updated_conversation)
```

---

## 6.3 Flux : sélection d'un client LLM

```
get_llm_client(provider_config)
    │
    ├─► provider_config.provider_type == OPENAI
    │       └─► import langchain_openai (lazy)
    │               ├─► ImportError → MissingDependencyError reformaté
    │               └─► return OpenAIClient(provider_config)
    │
    ├─► provider_config.provider_type == ANTHROPIC
    │       └─► import anthropic (lazy)
    │               └─► return AnthropicClient(provider_config)
    │
    ├─► provider_config.provider_type == OLLAMA
    │       └─► import ollama (lazy)
    │               └─► return OllamaClient(provider_config)
    │
    ├─► provider_config.provider_type == CUSTOM
    │       └─► lève UnsupportedProviderError
    │           ("Custom providers must be registered separately")
    │
    └─► [autre type]
            └─► lève UnsupportedProviderError
                (liste des types supportés dans le message)
```

Les imports sont **lazy** (dans le corps de la factory, pas au niveau module).
Cela signifie que si `openai` n'est pas installé, l'erreur n'est levée qu'au
moment d'utiliser `ProviderType.OPENAI`, pas à l'import du package.

---

## 6.4 Flux : stockage SQLite — `save_agent()`

```
SQLiteStorage.save_agent(agent)
    │
    ├─► agent.updated_at = datetime.now(UTC)
    │
    ├─► _serialize(agent) → JSON string
    │       └─► agent.model_dump_json()
    │           ← '{"id":"...","name":"...","role":"researcher",...}'
    │
    └─► SQL UPSERT :
        INSERT INTO agents (id, slug, owner_id, role, is_active, data)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            slug=excluded.slug,
            owner_id=excluded.owner_id,
            role=excluded.role,
            is_active=excluded.is_active,
            data=excluded.data
```

Et pour la lecture :

```
SQLiteStorage.get_agent(agent_id)
    │
    ├─► SELECT data FROM agents WHERE id = ?
    │
    ├─► row["data"] → JSON string
    │
    └─► Agent.model_validate_json(row["data"])
            ← Agent(id="...", name="...", role=AgentRole.RESEARCHER, ...)
```

---

## 6.5 Flux : streaming LLM

Le streaming permet de recevoir la réponse au fur et à mesure, sans attendre
la complétion totale. Utile pour les interfaces utilisateur temps réel.

```python
# Côté appelant
request = LLMRequest(messages=[...], stream=True)

# Sync streaming
for chunk in client.stream(request):
    print(chunk.delta, end="", flush=True)
    if chunk.finish_reason:
        break

# Async streaming
async for chunk in await client.astream(request):
    await websocket.send(chunk.delta)
```

Les chunks sont des `StreamChunk` :
```
StreamChunk(delta="La ")
StreamChunk(delta="réponse ")
StreamChunk(delta="est...")
StreamChunk(delta="", finish_reason="stop")
```

`validate_capabilities()` est appelé avant le streaming pour vérifier que
le provider supporte cette fonctionnalité (`capabilities.streaming=True`).

---

## 6.6 Cycle de vie des entités

### Agent

```
[Création]  → save_agent()    → is_active=True, created_at=now
[Lecture]   → get_agent()     → Agent complet
[Update]    → update_agent()  → champs modifiés + updated_at=now
[Désactiver]→ update_agent(is_active=False)
[Suppression]→ delete_agent() → retourne True, référencé par Conversation mais non cascade
```

### Conversation

```
[Création]  → save_conversation()  → status=ACTIVE
[Messages]  → save_message()       → message_count++, total_tokens++
[Archivage] → update status=ARCHIVED
[Suppression]→ delete_conversation() → messages orphelins (à gérer manuellement)
```

### Execution

```
[Création]  → status=PENDING
[Démarrage] → status=RUNNING, started_at=now
[Étapes]    → save_execution_step() pour chaque LLM/tool call
[Succès]    → status=SUCCESS, completed_at=now, output_data rempli
[Échec]     → status=FAILED, error rempli
[Annulation]→ status=CANCELLED
```

---

## 6.7 Interactions entre entités (références par ID)

Le package utilise des **références par UUID string** au lieu de jointures ORM.
Voici le graphe des dépendances :

```
LLMProviderConfig  ←──── Agent (provider_id)
                         │
                         ├── Conversation (agent_id)
                         │       └── Message (conversation_id)
                         │
                         ├── Execution (agent_id)
                         │       └── ExecutionStep (execution_id)
                         │
                         ├── AgentMemory (agent_id)
                         │
                         ├── Graph (agent_id)
                         │       ├── GraphNode
                         │       └── GraphEdge
                         │
                         ├─── [tool_ids] ───► ToolDefinition
                         │
                         └─── [skill_ids] ──► Skill ←── AgentSkillAssignment
                                              │
                                              └── [required_tool_ids] ──► ToolDefinition

KnowledgeSource (indépendant)
    ├── Document
    │       └── Chunk (avec embedding)
    └── [agent_ids] référencés par Agent.knowledge_base_ids
```

Conséquences architecturales :
- Pas de chargement en cascade automatique
- Le storage résout les références explicitement (ex: `list_tools_for_agent()`)
- Pas d'intégrité référentielle garantie (à gérer dans les services)
- Les suppressions sont explicites et ne cascadent pas

---

## 6.8 Gestion des erreurs dans les flux

Chaque couche a sa responsabilité dans la propagation des erreurs :

| Couche | Responsabilité |
|---|---|
| **Service** | Lever des exceptions métier typées (`AgentNotFoundError`, etc.) |
| **Client LLM** | Wrapper les erreurs provider en `LLMError` |
| **Storage** | Lever `StorageError` / `StorageConnectionError` en cas de problème de persistence |
| **Factory** | Reformater les `ImportError` en messages explicites avec commande d'installation |

Les consommateurs du package peuvent gérer les erreurs de manière granulaire :

```python
from ai_engine.exceptions import (
    AgentNotFoundError,
    ProviderNotFoundError,
    LLMError,
    StorageError,
)

try:
    response, conv = service.chat(agent_id=..., message=...)
except AgentNotFoundError as e:
    print(f"Agent {e.agent_id} non trouvé")
except LLMError as e:
    print(f"Erreur LLM : {e}")
except StorageError as e:
    print(f"Problème de persistence : {e}")
```
