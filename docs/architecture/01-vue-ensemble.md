# 01 — Vue d'ensemble de l'architecture

## 1.1 Objectif et positionnement

`ai-engine` est un **package Python standalone** d'orchestration d'agents LLM. Son objectif
principal est de découpler la logique IA de tout framework applicatif.

Là où son prédécesseur `django-ai-app` était fortement couplé à Django (ORM, migrations,
`models.Model`, `request.user`), `ai-engine` repose sur :
- **Pydantic v2** comme seule dépendance fondamentale (modelisation + validation)
- Une **interface de stockage abstraite** (`StorageBackend`) interchangeable
- Des **dépendances optionnelles** pour chaque provider LLM

```
pip install ai-engine            # noyau uniquement (Pydantic)
pip install ai-engine[openai]    # + client OpenAI
pip install ai-engine[anthropic] # + client Anthropic
pip install ai-engine[sqlite]    # + stockage SQLite (aiosqlite)
pip install ai-engine[all]       # tout inclus
```

---

## 1.2 Principes directeurs

| Principe | Application concrète |
|---|---|
| **Framework-agnostic** | Aucune dépendance Django/FastAPI dans le noyau |
| **Dépendances optionnelles** | Chaque provider LLM est un extra optionnel |
| **Type Safety** | Pydantic v2 + mypy strict sur tout le code |
| **Ports & Adapters** | `StorageBackend` est un port ; `InMemoryStorage`, `SQLiteStorage` sont des adapters |
| **Injection de dépendance** | `AgentService(storage)` — le storage est injecté, jamais instancié en dur |
| **Exceptions typées** | Jamais de `raise Exception(...)` nu — hiérarchie complète dans `exceptions.py` |
| **Immutabilité des IDs** | Les relations entre entités sont des références par `str` (UUID) — pas de FK |
| **Zero configuration** | `InMemoryStorage` fonctionne sans aucune config ; `SQLiteStorage` crée sa DB automatiquement |

---

## 1.3 Architecture en couches

Le package s'organise en **4 couches verticales** bien délimitées :

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CONSOMMATEURS (externe)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │  Django  │  │  FastAPI │  │  Script  │  │  Jupyter / Lambda  │  │
│  │ (futur)  │  │ (futur)  │  │   .py    │  │                    │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬───────────┘  │
└───────┼─────────────┼─────────────┼─────────────────┼──────────────┘
        └─────────────┴─────────────┴─────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                    COUCHE SERVICES                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  AgentService  ─────────────────────────────────────────────    │ │
│  │  • create_agent()  • chat()  • get_agent_stats()                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  LLM Clients (services/llm/)                                    │ │
│  │  LLMClient (ABC) → OpenAIClient / AnthropicClient / OllamaClient│ │
│  │                  → GroqClient / GeminiClient                    │ │
│  │  get_llm_client(provider_config) — Factory Pattern              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                    COUCHE MODÈLES (Pydantic)                          │
│                                                                       │
│  LLMProviderConfig   Agent+AgentConfig   Conversation   Message       │
│  ToolDefinition      Skill+Assignment    Execution      ExecutionStep │
│  AgentMemory         Graph+Node+Edge     KnowledgeSource Document     │
│  ToolCall            ToolResult          TokenUsage      Chunk        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                    COUCHE STOCKAGE (pluggable)                        │
│                                                                       │
│  StorageBackend (ABC)                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │  InMemoryStorage│  │  SQLiteStorage  │  │  [futur] Django ORM │   │
│  │  (tests/proto)  │  │  (CLI/scripts)  │  │  SQLAlchemy / JSON  │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 1.4 Structure des fichiers

```
src/ai_engine/
├── __init__.py              # API publique — façade d'import unique
├── config.py                # Settings via Pydantic Settings (env vars)
├── exceptions.py            # Hiérarchie complète d'exceptions typées
├── types.py                 # Enums partagés (ProviderType, AgentRole, etc.)
│
├── models/                  # Entités du domaine (Pydantic BaseModel)
│   ├── agent.py             # Agent, AgentConfig
│   ├── conversation.py      # Conversation
│   ├── execution.py         # Execution, ExecutionStep
│   ├── graph.py             # Graph, GraphNode, GraphEdge
│   ├── knowledge.py         # KnowledgeSource, Document, Chunk
│   ├── memory.py            # AgentMemory
│   ├── message.py           # Message, ToolCall, ToolResult, TokenUsage
│   ├── provider.py          # LLMProviderConfig, ProviderCapabilities, ...
│   ├── skill.py             # Skill, AgentSkillAssignment
│   └── tool.py              # ToolDefinition
│
├── services/                # Logique métier pure
│   ├── agent.py             # AgentService (CRUD agents + conversations + chat)
│   └── llm/                 # Abstraction clients LLM
│       ├── base.py          # LLMClient (ABC), LLMRequest, LLMResponse, StreamChunk
│       ├── factory.py       # get_llm_client() — sélection dynamique du client
│       ├── openai.py        # OpenAIClient
│       ├── anthropic.py     # AnthropicClient
│       ├── ollama.py        # OllamaClient
│       ├── groq.py          # GroqClient
│       └── gemini.py        # GeminiClient
│
└── storage/                 # Persistence (pattern Port & Adapter)
    ├── base.py              # StorageBackend (ABC) — contrat complet CRUD
    ├── memory.py            # InMemoryStorage — dict Python, sans persist
    └── sqlite.py            # SQLiteStorage — JSON sérialisé + index SQL
```

---

## 1.5 Dépendances et leur rôle

### Dépendances obligatoires

| Package | Version | Rôle |
|---|---|---|
| `pydantic` | ≥2.0, <3.0 | Validation, sérialisation, modèles de domaine |
| `pydantic-settings` | ≥2.0 | Lecture des variables d'environnement (`Settings`) |

### Dépendances optionnelles

| Extra pip | Package | Activé par |
|---|---|---|
| `[openai]` | `langchain-openai` | `OpenAIClient` |
| `[anthropic]` | `langchain-anthropic` | `AnthropicClient` |
| `[ollama]` | `langchain-ollama` | `OllamaClient` |
| `[sqlite]` | `aiosqlite` | `SQLiteStorage` async |
| `[sqlalchemy]` | `sqlalchemy[asyncio]`, `asyncpg` | Futur `SQLAlchemyStorage` |
| `[embeddings]` | `sentence-transformers` | Futur service d'embeddings |
| `[langchain]` | `langchain-core`, `langgraph` | Futur runtime de graphs |
| `[fastapi]` | `fastapi`, `uvicorn` | Futur adapter FastAPI |
| `[django]` | `django`, `djangorestframework` | Futur adapter Django |

### Tooling de développement

| Outil | Rôle |
|---|---|
| `pytest` + `pytest-asyncio` | Tests unitaires et d'intégration |
| `ruff` | Linting et formatage (remplace flake8 + isort + black) |
| `mypy` (strict) | Vérification statique des types |

### Compatibilité Python

Le package supporte **Python 3.11, 3.12 et 3.13**.

---

## 1.6 Origines : migration depuis Django

`ai-engine` est une extraction de `django-ai-app`. Voici le mapping des patterns Django vers Python pur :

| Pattern Django | Équivalent ai-engine |
|---|---|
| `models.Model` | `pydantic.BaseModel` |
| `ForeignKey(Agent)` | `agent_id: str` (référence par UUID) |
| `ManyToManyField` | `tool_ids: list[str]` |
| `JSONField` | Sous-modèle Pydantic typé |
| `FileField` | `file_path: str \| None` |
| `UUIDField` | `id: str = Field(default_factory=lambda: str(uuid4()))` |
| `TextChoices` | `class MyEnum(StrEnum)` |
| `TimeStampedModel` | `created_at/updated_at: datetime` explicites |
| `settings.AUTH_USER_MODEL` | `owner_id: str \| None` |
| `Agent.objects.get(slug=...)` | `storage.get_agent_by_slug(slug)` |
| `agent.tools.filter(is_active=True)` | `storage.list_tools_for_agent(agent_id)` |
