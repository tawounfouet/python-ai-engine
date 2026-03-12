# Plan d'implémentation — `ai_engine` (Package Python Standalone)

> **Objectif** : Extraire la logique AI de l'app Django `django-ai-app` vers un package Python
> standalone, réutilisable dans n'importe quel contexte (scripts, notebooks, FastAPI, Django, CLI, Lambda, etc.)

---

## Table des matières

1. [État des lieux — App Django actuelle](#1-état-des-lieux--app-django-actuelle)
2. [Architecture cible](#2-architecture-cible)
3. [Mapping détaillé Django → Standalone](#3-mapping-détaillé-django--standalone)
4. [Plan de migration par phases](#4-plan-de-migration-par-phases)
5. [Phase 1 — Structure & Models Pydantic](#5-phase-1--structure--models-pydantic)
6. [Phase 2 — Storage Layer (Persistence abstraite)](#6-phase-2--storage-layer-persistence-abstraite)
7. [Phase 3 — Services (logique métier pure)](#7-phase-3--services-logique-métier-pure)
8. [Phase 4 — Tools, Skills & Events](#8-phase-4--tools-skills--events)
9. [Phase 5 — Adapters (Django, FastAPI)](#9-phase-5--adapters-django-fastapi)
10. [Phase 6 — Tests & Packaging](#10-phase-6--tests--packaging)
11. [Conventions & Règles](#11-conventions--règles)
12. [Exemples d'utilisation finale](#12-exemples-dutilisation-finale)
13. [Risques & Mitigations](#13-risques--mitigations)
14. [Checklist de validation](#14-checklist-de-validation)

---

## 1. État des lieux — App Django actuelle

### 1.1 Inventaire des composants

| Composant Django | Fichier(s) | Dépendances Django | Complexité |
|---|---|---|---|
| `Provider` model | `models/provider.py` | `models.Model`, `UUIDField`, `JSONField` | Moyenne |
| `Agent` model | `models/agent.py` | `models.Model`, `ForeignKey`, `M2M`, `TimeStampedModel` | Haute |
| `Tool` model | `models/tool.py` | `models.Model`, `SlugField`, `JSONField` | Moyenne |
| `Skill` + `AgentSkill` | `models/skill.py` | `models.Model`, `M2M through`, `ForeignKey` | Haute |
| `Graph` model | `models/graph.py` | `models.Model`, `ForeignKey`, `JSONField` | Moyenne |
| `Execution` + `ExecutionStep` | `models/execution.py` | `models.Model`, `ForeignKey`, `DecimalField` | Haute |
| `AgentMessage` | `models/message.py` | `models.Model`, `ForeignKey`, `settings.AUTH_USER_MODEL` | Moyenne |
| `AgentMemory` | `models/memory.py` | `models.Model`, `ForeignKey`, `JSONField` | Moyenne |
| `KnowledgeSource` | `models/knowledge.py` | `models.Model`, `FileField`, `M2M` | Haute |
| LLM Factory | `llm.py` | Importe `Provider` Django, LangChain | Haute |
| Agent Factory | `agents.py` | Importe `Agent` Django, LangGraph, `utils.py` | Haute |
| Graph Runtime | `graph_runtime.py` | Importe `Agent`, `Graph` Django, LangGraph Supervisor | Haute |
| Utils | `utils.py` | Importe `Agent`, `Tool` Django, `importlib` | Moyenne |
| Tools | `tools/` | LangChain `@tool`, `RunnableConfig` | Moyenne |
| Skills | `skills/` | ABC, `SkillRegistry`, `BaseChatModel` | Moyenne |
| Views (API) | `views.py` | DRF, `permissions`, `serializers`, `APIView` | Haute |
| Admin | `admin.py` | `django.contrib.admin` | Basse |

### 1.2 Dépendances directes Django identifiées

```
django.db.models.Model          → Pydantic BaseModel
django.db.models.ForeignKey     → str (ID reference)
django.db.models.ManyToManyField → list[str] (ID list)
django.db.models.JSONField      → dict / Pydantic nested model
django.db.models.FileField      → str (path) ou bytes
django.db.models.UUIDField      → str (uuid4)
django.db.models.TextChoices    → enum.Enum (str, Enum)
django.conf.settings             → ai_engine.config.Settings
django.contrib.auth.User        → owner_id: str | None
core.models.TimeStampedModel    → created_at/updated_at fields
```

### 1.3 Points de couplage critiques

1. **`llm.py`** — Reçoit un objet `Provider` Django, accède à `.secrets`, `.config`, `.model_name`
2. **`agents.py`** — Fait `Agent.objects.select_related("provider").get(slug=...)` directement
3. **`graph_runtime.py`** — Orchestre via `Agent.objects.get()` et `Graph.objects.get()`
4. **`utils.py`** — `Agent.objects.get()`, `agent.tools.filter(is_active=True)`
5. **`views.py`** — DRF views, `request.user`, JWT auth
6. **`tools/base.py`** — Extraction de `user_id` depuis `RunnableConfig`

---

## 2. Architecture cible

### 2.1 Diagramme principal

```
┌──────────────────────────────────────────────────────────────────┐
│                        CONSUMERS                                 │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Django │ │FastAPI │ │ Script │ │ Notebook │ │ CLI / Lambda│ │
│  │adapter │ │adapter │ │  .py   │ │ .ipynb   │ │             │ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └────┬─────┘ └──────┬──────┘ │
│      └──────────┴──────────┴───────────┴──────────────┘         │
│                            │                                     │
│  ┌─────────────────────────▼───────────────────────────────────┐ │
│  │              ai_engine (Public API)                          │ │
│  │  __init__.py — façade unique d'import                       │ │
│  └─────────────────────────┬───────────────────────────────────┘ │
│                            │                                     │
│     ┌──────────────────────┼──────────────────────┐              │
│     ▼                      ▼                      ▼              │
│  ┌────────────┐    ┌──────────────┐    ┌───────────────┐        │
│  │   Models   │    │   Services   │    │   Events      │        │
│  │ (Pydantic) │    │  (Pure Py)   │    │   (EventBus)  │        │
│  │            │    │              │    │               │        │
│  │ Provider   │    │ LLM Factory  │    │ on/emit/off   │        │
│  │ Agent      │    │ AgentService │    │               │        │
│  │ Tool       │    │ GraphRuntime │    └───────────────┘        │
│  │ Skill      │    │ SkillRunner  │                              │
│  │ Graph      │    │ KnowledgeSvc │    ┌───────────────┐        │
│  │ Execution  │    │              │    │    Tools      │        │
│  │ Message    │    └──────┬───────┘    │  (Registry)   │        │
│  │ Memory     │           │            │  base, web,   │        │
│  │ Knowledge  │           │            │  http, text   │        │
│  └────────────┘           │            └───────────────┘        │
│                           │                                      │
│  ┌────────────────────────▼──────────────────────────────────┐  │
│  │              Storage Interface (ABC)                        │  │
│  │                                                            │  │
│  │  ┌───────────┐  ┌─────────┐  ┌──────────┐  ┌───────────┐ │  │
│  │  │ InMemory  │  │ SQLite  │  │ JSON File│  │ SQLAlchemy│ │  │
│  │  │ (tests)   │  │ (local) │  │ (proto)  │  │ (Postgres)│ │  │
│  │  └───────────┘  └─────────┘  └──────────┘  └───────────┘ │  │
│  │  ┌─────────────────┐                                       │  │
│  │  │ Django ORM      │ ← adapter, pas dans le core           │  │
│  │  └─────────────────┘                                       │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Structure de fichiers

```
ai_engine/
├── src/
│   └── ai_engine/
│       ├── __init__.py                  # API publique (façade)
│       ├── config.py                    # Settings (env vars, fichiers TOML/YAML)
│       ├── exceptions.py               # Exceptions métier typées
│       ├── types.py                     # Types communs, Enums partagés
│       │
│       ├── models/                      # ── Pydantic Models (domaine) ──
│       │   ├── __init__.py              # Re-exports
│       │   ├── provider.py              # LLMProviderConfig, ProviderType
│       │   ├── agent.py                 # Agent, AgentConfig, AgentRole
│       │   ├── tool.py                  # ToolDefinition, ToolType
│       │   ├── skill.py                 # Skill, SkillCategory, AgentSkill
│       │   ├── conversation.py          # Conversation, ConversationStatus
│       │   ├── message.py               # Message, MessageRole, ToolCall, ToolResult
│       │   ├── graph.py                 # Graph, GraphNode, GraphEdge, NodeType
│       │   ├── execution.py             # Execution, ExecutionStep, ExecutionStatus, TokenUsage
│       │   ├── memory.py               # AgentMemory, MemoryType
│       │   └── knowledge.py             # KnowledgeSource, SourceType, IndexStatus, Document, Chunk
│       │
│       ├── services/                    # ── Logique métier pure ──
│       │   ├── __init__.py
│       │   ├── llm/                     # Abstraction LLM providers
│       │   │   ├── __init__.py
│       │   │   ├── base.py              # LLMClient (ABC), LLMResponse
│       │   │   ├── openai.py            # OpenAIClient
│       │   │   ├── anthropic.py         # AnthropicClient
│       │   │   ├── ollama.py            # OllamaClient
│       │   │   ├── openai_compatible.py # Client générique OpenAI-compatible
│       │   │   └── factory.py           # LLMClientFactory (registry pattern)
│       │   │
│       │   ├── agent_service.py         # Orchestration agent (chat, tool loop)
│       │   ├── conversation_service.py  # CRUD conversations + messages
│       │   ├── graph_runtime.py         # Exécution graphs multi-agents
│       │   ├── skill_runner.py          # Exécution de skills
│       │   ├── knowledge_service.py     # RAG : ingestion, embedding, retrieval
│       │   └── execution_tracker.py     # Suivi d'exécution, métriques, coûts
│       │
│       ├── storage/                     # ── Persistence (pluggable) ──
│       │   ├── __init__.py              # Re-exports
│       │   ├── base.py                  # StorageBackend (ABC) — contrat complet
│       │   ├── memory.py               # InMemoryStorage (tests, prototypage)
│       │   ├── sqlite.py               # SQLiteStorage (usage local, CLI)
│       │   ├── json_file.py            # JSONFileStorage (debug, export)
│       │   └── sqlalchemy.py           # SQLAlchemyStorage (PostgreSQL, MySQL, etc.)
│       │
│       ├── tools/                       # ── Tools (function calling) ──
│       │   ├── __init__.py
│       │   ├── base.py                  # Tool (ABC), ToolParameter, ToolResult
│       │   ├── registry.py              # ToolRegistry (enregistrement/résolution)
│       │   ├── decorators.py            # @tool decorator (à la LangChain)
│       │   ├── web_search.py            # Exemple : recherche web
│       │   ├── http_client.py           # Exemple : appels HTTP
│       │   ├── text_processing.py       # Exemple : traitement texte
│       │   └── calculator.py            # Exemple : calculs
│       │
│       ├── skills/                      # ── Skills (capacités haut niveau) ──
│       │   ├── __init__.py
│       │   ├── base.py                  # BaseSkill (ABC), SkillRegistry
│       │   ├── research.py              # ResearchSkill
│       │   ├── analysis.py              # AnalysisSkill
│       │   ├── coding.py               # CodingSkill
│       │   └── communication.py         # CommunicationSkill
│       │
│       ├── embeddings/                  # ── Abstraction Embeddings ──
│       │   ├── __init__.py
│       │   ├── base.py                  # EmbeddingClient (ABC)
│       │   ├── openai.py               # OpenAIEmbedding
│       │   └── sentence_transformers.py # Local sentence-transformers
│       │
│       ├── events/                      # ── Système d'événements ──
│       │   ├── __init__.py
│       │   ├── bus.py                   # EventBus (remplace django.dispatch.Signal)
│       │   └── events.py               # Définitions d'événements typés
│       │
│       └── adapters/                    # ── Intégrations framework ──
│           ├── __init__.py
│           ├── django/                  # Adapter Django
│           │   ├── __init__.py
│           │   ├── apps.py              # Django AppConfig
│           │   ├── models.py            # Django ORM models (miroir des Pydantic)
│           │   ├── storage.py           # DjangoORMStorage(StorageBackend)
│           │   ├── admin.py             # Admin registration
│           │   ├── serializers.py       # DRF serializers
│           │   ├── views.py             # DRF viewsets
│           │   ├── signals.py           # Django signals → EventBus bridge
│           │   └── migrations/          # Django migrations
│           │
│           └── fastapi/                 # Adapter FastAPI
│               ├── __init__.py
│               ├── router.py            # FastAPI APIRouter
│               ├── dependencies.py      # Dependency injection (Depends)
│               └── schemas.py           # Response schemas (hérités des models)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures communes (InMemoryStorage, mock LLM)
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── test_provider.py
│   │   │   ├── test_agent.py
│   │   │   ├── test_message.py
│   │   │   ├── test_graph.py
│   │   │   └── test_execution.py
│   │   ├── services/
│   │   │   ├── test_agent_service.py
│   │   │   ├── test_llm_factory.py
│   │   │   ├── test_graph_runtime.py
│   │   │   └── test_execution_tracker.py
│   │   ├── test_tool_registry.py
│   │   ├── test_skill_registry.py
│   │   └── test_event_bus.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_sqlite_storage.py
│   │   ├── test_json_file_storage.py
│   │   ├── test_full_conversation.py
│   │   └── test_multi_agent_graph.py
│   └── adapters/
│       ├── __init__.py
│       ├── test_django_storage.py
│       └── test_fastapi_router.py
│
├── examples/
│   ├── 01_basic_chat.py                 # Chat simple avec un agent
│   ├── 02_agent_with_tools.py           # Agent avec function calling
│   ├── 03_multi_agent_graph.py          # Workflow multi-agents
│   ├── 04_rag_knowledge_base.py         # RAG avec knowledge sources
│   ├── 05_custom_storage.py             # Implémentation d'un storage custom
│   ├── 06_custom_tool.py               # Création d'un tool custom
│   ├── 07_django_integration.py         # Intégration dans un projet Django
│   ├── 08_fastapi_integration.py        # Intégration dans une app FastAPI
│   └── 09_notebook_demo.ipynb           # Démo interactive Jupyter
│
├── pyproject.toml                       # Build, dépendances, extras
├── README.md
├── LICENSE
└── CHANGELOG.md
```

---

## 3. Mapping détaillé Django → Standalone

### 3.1 Models

#### `Provider` → `LLMProviderConfig`

| Champ Django | Type Django | Champ Pydantic | Type Pydantic | Notes |
|---|---|---|---|---|
| `id` | `UUIDField` | `id` | `str` (uuid4) | `default_factory` |
| `name` | `CharField` | `name` | `str` | |
| `provider_type` | `CharField(choices)` | `provider_type` | `ProviderType(str, Enum)` | |
| `description` | `TextField` | `description` | `str = ""` | |
| `model_name` | `CharField` | `default_model` | `str` | Renommé pour clarté |
| `config` | `JSONField` | `config` | `ProviderSettings` (Pydantic nested) | Typé proprement |
| `secrets` | `JSONField` | `api_key` + `api_base_url` + `extra_secrets` | `SecretStr`, `str`, `dict` | Champs explicites |
| `is_active` | `BooleanField` | `is_active` | `bool = True` | |
| `is_default` | `BooleanField` | `is_default` | `bool = False` | |
| `supports_vision` | `BooleanField` | `capabilities.vision` | `ProviderCapabilities` (nested) | Groupé |
| `supports_function_calling` | `BooleanField` | `capabilities.function_calling` | `ProviderCapabilities` (nested) | Groupé |
| `supports_streaming` | `BooleanField` | `capabilities.streaming` | `ProviderCapabilities` (nested) | Groupé |
| `context_window` | `IntegerField` | `capabilities.context_window` | `ProviderCapabilities` (nested) | Groupé |
| `cost_per_1k_input` | `DecimalField` | `pricing.input_per_1k` | `PricingConfig` (nested) | Groupé |
| `cost_per_1k_output` | `DecimalField` | `pricing.output_per_1k` | `PricingConfig` (nested) | Groupé |
| `usage_count` | `IntegerField` | — | — | Géré par `ExecutionTracker` |
| `total_tokens` | `BigIntegerField` | — | — | Géré par `ExecutionTracker` |
| `total_cost` | `DecimalField` | — | — | Géré par `ExecutionTracker` |
| `created_at` | auto | `created_at` | `datetime` | |
| `updated_at` | auto | `updated_at` | `datetime` | |

#### `Agent` → `Agent`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `id` (UUID) | `id: str` | |
| `name` | `name: str` | |
| `slug` | `slug: str` | Conservé pour compat |
| `description` | `description: str` | |
| `role` (TextChoices) | `role: AgentRole` (Enum) | |
| `provider` (FK) | `provider_id: str` | Référence par ID |
| `system_prompt` | `system_prompt: str` | |
| `welcome_message` | `welcome_message: str` | |
| `config` (JSON) | `config: AgentConfig` | Pydantic nested, typé |
| `tools` (M2M) | `tool_ids: list[str]` | Liste d'IDs |
| `skills` (M2M through) | `skill_ids: list[str]` | Liste d'IDs |
| `is_active` | `is_active: bool` | |
| `max_iterations` | `config.max_iterations: int` | Dans AgentConfig |
| `max_tokens_per_run` | `config.max_tokens_per_run: int` | Dans AgentConfig |
| `total_runs` | — | Géré par ExecutionTracker |
| `total_tokens_used` | — | Géré par ExecutionTracker |
| — (User FK implicite) | `owner_id: str \| None` | Framework-agnostic |

#### `Tool` → `ToolDefinition`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `id` (UUID) | `id: str` | |
| `key` (Slug) | `key: str` | Identifiant unique |
| `name` | `name: str` | |
| `description` | `description: str` | Pour le LLM (function calling) |
| `tool_type` (TextChoices) | `tool_type: ToolType` (Enum) | |
| `parameters_schema` (JSON) | `parameters_schema: dict` | JSON Schema OpenAI format |
| `function_path` | `function_path: str` | Chemin d'import Python |
| `connector_id` | `connector_id: str \| None` | |
| `config` (JSON) | `config: dict` | |
| `requires_approval` | `requires_approval: bool` | |
| `is_dangerous` | `is_dangerous: bool` | |
| `is_active` | `is_active: bool` | |

#### `Skill` + `AgentSkill` → `Skill` + `AgentSkillAssignment`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `Skill.key` | `key: str` | |
| `Skill.name` | `name: str` | |
| `Skill.category` | `category: SkillCategory` (Enum) | |
| `Skill.system_prompt` | `system_prompt: str` | |
| `Skill.required_tools` (M2M) | `required_tool_ids: list[str]` | |
| `Skill.recommended_provider` (FK) | `recommended_provider_id: str \| None` | |
| `AgentSkill.proficiency` | `AgentSkillAssignment.proficiency: Proficiency` (Enum) | |
| `AgentSkill.provider_override` (FK) | `AgentSkillAssignment.provider_override_id: str \| None` | |
| `AgentSkill.enabled` | `AgentSkillAssignment.enabled: bool` | |

#### `Graph` → `Graph`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `id` (UUID) | `id: str` | |
| `name` | `name: str` | |
| `slug` | `slug: str` | |
| `description` | `description: str` | |
| `agent` (FK) | `agent_id: str` | |
| `definition` (JSON) | `nodes: list[GraphNode]` + `edges: list[GraphEdge]` + `entry_node_id` | **Éclaté** en types forts |
| `status` (TextChoices) | `status: GraphStatus` (Enum) | |
| `version` | `version: int` | |

#### `Execution` + `ExecutionStep` → `Execution` + `ExecutionStep`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `Execution.status` | `status: ExecutionStatus` (Enum) | |
| `Execution.input_data` (JSON) | `input_data: dict` | |
| `Execution.output_data` (JSON) | `output_data: dict` | |
| `Execution.total_tokens` | `token_usage: TokenUsage` (nested) | Typé |
| `Execution.total_cost` | `token_usage.estimated_cost_usd` | Dans TokenUsage |
| `ExecutionStep.step_type` | `step_type: StepType` (Enum) | |
| `ExecutionStep.tool` (FK) | `tool_id: str \| None` | |
| `ExecutionStep.duration_ms` | `duration_ms: int` | |

#### `AgentMessage` → `Message`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `execution` (FK) | `conversation_id: str` | Renommé : concept Conversation |
| `role` (TextChoices) | `role: MessageRole` (Enum) | |
| `content` | `content: str` | |
| `metadata` (JSON) | `tool_calls: list[ToolCall]` + `tool_result: ToolResult \| None` + `metadata: dict` | **Éclaté** en types forts |
| `tokens` | `token_usage: TokenUsage \| None` | Typé |
| `order` | — | Ordre implicite par `created_at` |

#### `AgentMemory` → `AgentMemory`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `agent` (FK) | `agent_id: str` | |
| `memory_type` (TextChoices) | `memory_type: MemoryType` (Enum) | |
| `key` | `key: str` | |
| `content` | `content: str` | |
| `embedding` (JSON) | `embedding: list[float] \| None` | Typé |
| `relevance_score` | `relevance_score: float` | |
| `expires_at` | `expires_at: datetime \| None` | |

#### `KnowledgeSource` → `KnowledgeSource`

| Champ Django | Champ Pydantic | Notes |
|---|---|---|
| `source_type` | `source_type: SourceType` (Enum) | |
| `content` | `content: str` | |
| `file` (FileField) | `file_path: str \| None` | Chemin, pas FileField |
| `url` | `url: str \| None` | |
| `index_status` | `index_status: IndexStatus` (Enum) | |
| `chunks_count` | `chunks_count: int` | |
| `agents` (M2M) | `agent_ids: list[str]` | |

### 3.2 Services

| Service Django | Fichier actuel | Service Standalone | Changements clés |
|---|---|---|---|
| LLM Factory | `llm.py` | `services/llm/factory.py` | Reçoit `LLMProviderConfig` Pydantic au lieu de `Provider` Django |
| LLM Builders | `llm.py` (_register) | `services/llm/openai.py`, etc. | Chaque provider dans son fichier, même pattern registry |
| Agent Factory | `agents.py` | `services/agent_service.py` | Reçoit `Agent` + `StorageBackend` au lieu de `Agent.objects.get()` |
| Graph Runtime | `graph_runtime.py` | `services/graph_runtime.py` | Reçoit des objets via storage, pas via ORM |
| Utils (get_llm) | `utils.py` | Intégré dans `services/llm/factory.py` | Plus de `Agent.objects.get()` |
| Utils (load_tools) | `utils.py` | `tools/registry.py` + `tools/loader.py` | Chargement via ToolRegistry, pas via ORM |
| Tools base | `tools/base.py` | `tools/base.py` | Plus de dépendance à `RunnableConfig` Django |
| Skills base | `skills/base.py` | `skills/base.py` | Idem, `SkillRegistry` standalone |

### 3.3 Patterns Django → Patterns Standalone

| Pattern Django | Pattern Standalone | Implémentation |
|---|---|---|
| `models.Model` | `pydantic.BaseModel` | Validation, serialization JSON native |
| `Model.objects.get()` | `storage.get_agent(id)` | Interface abstraite |
| `Model.objects.filter()` | `storage.list_agents(filters)` | Méthodes filtrées |
| `ForeignKey` | `field_id: str` | Référence par ID |
| `ManyToManyField` | `field_ids: list[str]` | Liste d'IDs |
| `django.dispatch.Signal` | `EventBus.on() / .emit()` | Callbacks simples |
| `django.conf.settings` | `ai_engine.config.Settings` | Pydantic Settings, env vars |
| `@transaction.atomic` | Context manager dans storage | `storage.transaction()` |
| Django Admin | — (via adapter) | L'adapter Django reconstruit l'admin |
| DRF Serializers | — (Pydantic natif) | `.model_dump()` / `.model_validate()` |
| DRF ViewSets | — (via adapter) | L'adapter FastAPI/Django crée les routes |
| `request.user` | `owner_id: str \| None` | Passé explicitement |

---

## 4. Plan de migration par phases

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Phase 1 │ ──→ │ Phase 2 │ ──→ │ Phase 3 │ ──→ │ Phase 4 │ ──→ │ Phase 5 │ ──→ │ Phase 6 │
│         │     │         │     │         │     │         │     │         │     │         │
│ Models  │     │ Storage │     │Services │     │Tools    │     │Adapters │     │Tests    │
│Pydantic │     │  Layer  │     │ & LLM   │     │Skills   │     │Django   │     │Package  │
│         │     │         │     │         │     │Events   │     │FastAPI  │     │PyPI     │
│ ~3 jours│     │ ~4 jours│     │ ~5 jours│     │ ~3 jours│     │ ~4 jours│     │ ~3 jours│
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
                                                                                 
                                                                  Total estimé : ~22 jours
```

### Dépendances entre phases

```
Phase 1 (Models) ─────┐
                       ├──→ Phase 2 (Storage) ──→ Phase 3 (Services) ──┐
                       │                                                ├──→ Phase 5 (Adapters) ──→ Phase 6 (Tests & Package)
                       └──→ Phase 4 (Tools/Skills/Events) ─────────────┘
```

---

## 5. Phase 1 — Structure & Models Pydantic

### 5.1 Objectif
Créer la structure du package et convertir les 9 models Django en Pydantic models purs.

### 5.2 Livrables

| Fichier | Contenu | Priorité |
|---|---|---|
| `pyproject.toml` | Build system, dépendances, extras | P0 |
| `src/ai_engine/__init__.py` | API publique | P0 |
| `src/ai_engine/config.py` | Settings (Pydantic Settings) | P0 |
| `src/ai_engine/exceptions.py` | Exceptions métier | P0 |
| `src/ai_engine/types.py` | Enums partagés | P0 |
| `src/ai_engine/models/provider.py` | `LLMProviderConfig`, `ProviderType`, `ProviderCapabilities`, `PricingConfig` | P0 |
| `src/ai_engine/models/agent.py` | `Agent`, `AgentConfig`, `AgentRole` | P0 |
| `src/ai_engine/models/tool.py` | `ToolDefinition`, `ToolType` | P0 |
| `src/ai_engine/models/skill.py` | `Skill`, `SkillCategory`, `AgentSkillAssignment`, `Proficiency` | P1 |
| `src/ai_engine/models/conversation.py` | `Conversation`, `ConversationStatus` | P0 |
| `src/ai_engine/models/message.py` | `Message`, `MessageRole`, `ToolCall`, `ToolResult`, `TokenUsage` | P0 |
| `src/ai_engine/models/graph.py` | `Graph`, `GraphNode`, `GraphEdge`, `NodeType`, `GraphStatus` | P1 |
| `src/ai_engine/models/execution.py` | `Execution`, `ExecutionStep`, `ExecutionStatus`, `StepType` | P1 |
| `src/ai_engine/models/memory.py` | `AgentMemory`, `MemoryType` | P2 |
| `src/ai_engine/models/knowledge.py` | `KnowledgeSource`, `SourceType`, `IndexStatus`, `Document`, `Chunk` | P2 |

### 5.3 Règles de conversion

```python
# ── Règle 1 : ID toujours str (uuid4 par défaut) ──
id: str = Field(default_factory=lambda: str(uuid4()))

# ── Règle 2 : ForeignKey → str reference ──
# Django:  provider = models.ForeignKey("ai.Provider", ...)
# Pydantic:
provider_id: str

# ── Règle 3 : ManyToMany → list[str] ──
# Django:  tools = models.ManyToManyField("ai.Tool", ...)
# Pydantic:
tool_ids: list[str] = Field(default_factory=list)

# ── Règle 4 : TextChoices → str Enum ──
# Django:  class AgentRole(models.TextChoices): ...
# Pydantic:
class AgentRole(str, Enum): ...

# ── Règle 5 : JSONField dict → Pydantic nested model ──
# Django:  config = models.JSONField(default=dict)
# Pydantic:
class AgentConfig(BaseModel):
    max_iterations: int = 10
    temperature: float = 0.7
    ...
config: AgentConfig = Field(default_factory=AgentConfig)

# ── Règle 6 : Timestamps automatiques ──
created_at: datetime = Field(default_factory=datetime.now)
updated_at: datetime = Field(default_factory=datetime.now)

# ── Règle 7 : owner_id au lieu de User FK ──
# Django:  user = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
# Pydantic:
owner_id: str | None = None
```

### 5.4 Exemples de models convertis

```python
# ── models/provider.py ──
class ProviderType(str, Enum):
    OPENAI = "openai"
    OPENAI_AZURE = "openai_azure"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    BEDROCK = "bedrock"
    VERTEX_AI = "vertex_ai"
    VLLM = "vllm"
    CUSTOM = "custom"
    # ... tous les types de l'app Django

class ProviderCapabilities(BaseModel):
    vision: bool = False
    function_calling: bool = True
    streaming: bool = True
    context_window: int = 4096

class PricingConfig(BaseModel):
    input_per_1k_tokens: float = 0.0
    output_per_1k_tokens: float = 0.0
    currency: str = "USD"

class ProviderSettings(BaseModel):
    temperature: float = 0.7
    max_tokens: int | None = None
    max_retries: int = 2
    timeout: int = 30

class LLMProviderConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    provider_type: ProviderType
    description: str = ""
    default_model: str
    api_key: SecretStr | None = None
    api_base_url: str | None = None
    extra_secrets: dict = Field(default_factory=dict)
    settings: ProviderSettings = Field(default_factory=ProviderSettings)
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    pricing: PricingConfig = Field(default_factory=PricingConfig)
    is_active: bool = True
    is_default: bool = False
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

---

## 6. Phase 2 — Storage Layer (Persistence abstraite)

### 6.1 Objectif
Créer l'interface de persistence abstraite et 2 implémentations concrètes.

### 6.2 Interface `StorageBackend`

L'interface couvre **tous les models** avec des opérations CRUD standardisées :

```python
class StorageBackend(ABC):
    """Contrat de persistence — toute implémentation doit respecter cette interface."""

    # ── Providers ──
    def save_provider(self, provider: LLMProviderConfig) -> LLMProviderConfig: ...
    def get_provider(self, provider_id: str) -> LLMProviderConfig | None: ...
    def get_provider_by_name(self, name: str) -> LLMProviderConfig | None: ...
    def list_providers(self, is_active: bool | None = None) -> list[LLMProviderConfig]: ...
    def delete_provider(self, provider_id: str) -> bool: ...

    # ── Agents ──
    def save_agent(self, agent: Agent) -> Agent: ...
    def get_agent(self, agent_id: str) -> Agent | None: ...
    def get_agent_by_slug(self, slug: str) -> Agent | None: ...
    def list_agents(self, owner_id: str | None = None, role: AgentRole | None = None, is_active: bool | None = None) -> list[Agent]: ...
    def delete_agent(self, agent_id: str) -> bool: ...

    # ── Tools ──
    def save_tool(self, tool: ToolDefinition) -> ToolDefinition: ...
    def get_tool(self, tool_id: str) -> ToolDefinition | None: ...
    def get_tool_by_key(self, key: str) -> ToolDefinition | None: ...
    def list_tools(self, is_active: bool | None = None) -> list[ToolDefinition]: ...
    def list_tools_for_agent(self, agent_id: str) -> list[ToolDefinition]: ...
    def delete_tool(self, tool_id: str) -> bool: ...

    # ── Skills ──
    def save_skill(self, skill: Skill) -> Skill: ...
    def get_skill(self, skill_id: str) -> Skill | None: ...
    def list_skills_for_agent(self, agent_id: str) -> list[AgentSkillAssignment]: ...

    # ── Conversations ──
    def save_conversation(self, conversation: Conversation) -> Conversation: ...
    def get_conversation(self, conversation_id: str) -> Conversation | None: ...
    def list_conversations(self, agent_id: str | None = None, owner_id: str | None = None) -> list[Conversation]: ...
    def delete_conversation(self, conversation_id: str) -> bool: ...

    # ── Messages ──
    def save_message(self, message: Message) -> Message: ...
    def get_messages(self, conversation_id: str, limit: int | None = None, offset: int = 0) -> list[Message]: ...
    def count_messages(self, conversation_id: str) -> int: ...

    # ── Executions ──
    def save_execution(self, execution: Execution) -> Execution: ...
    def get_execution(self, execution_id: str) -> Execution | None: ...
    def list_executions(self, agent_id: str | None = None, status: ExecutionStatus | None = None) -> list[Execution]: ...
    def save_execution_step(self, step: ExecutionStep) -> ExecutionStep: ...
    def get_execution_steps(self, execution_id: str) -> list[ExecutionStep]: ...

    # ── Graphs ──
    def save_graph(self, graph: Graph) -> Graph: ...
    def get_graph(self, graph_id: str) -> Graph | None: ...
    def get_graph_by_slug(self, slug: str) -> Graph | None: ...
    def list_graphs(self, agent_id: str | None = None, owner_id: str | None = None) -> list[Graph]: ...
    def delete_graph(self, graph_id: str) -> bool: ...

    # ── Memory ──
    def save_memory(self, memory: AgentMemory) -> AgentMemory: ...
    def get_memory(self, agent_id: str, key: str) -> AgentMemory | None: ...
    def list_memories(self, agent_id: str, memory_type: MemoryType | None = None) -> list[AgentMemory]: ...
    def delete_memory(self, memory_id: str) -> bool: ...
    def delete_expired_memories(self) -> int: ...

    # ── Knowledge ──
    def save_knowledge_source(self, source: KnowledgeSource) -> KnowledgeSource: ...
    def get_knowledge_source(self, source_id: str) -> KnowledgeSource | None: ...
    def list_knowledge_sources(self, agent_id: str | None = None) -> list[KnowledgeSource]: ...
    def delete_knowledge_source(self, source_id: str) -> bool: ...
```

### 6.3 Implémentations prévues

| Backend | Fichier | Usage principal | Priorité |
|---|---|---|---|
| `InMemoryStorage` | `storage/memory.py` | Tests unitaires, prototypage rapide | P0 |
| `SQLiteStorage` | `storage/sqlite.py` | Scripts, CLI, usage local | P0 |
| `JSONFileStorage` | `storage/json_file.py` | Debug, export, notebooks | P1 |
| `SQLAlchemyStorage` | `storage/sqlalchemy.py` | Production (PostgreSQL, MySQL) | P2 |
| `DjangoORMStorage` | `adapters/django/storage.py` | Projets Django existants | P2 |

### 6.4 Stratégie SQLite

```python
class SQLiteStorage(StorageBackend):
    """Storage SQLite — zero-config, fichier unique, parfait pour CLI/scripts."""

    def __init__(self, db_path: str = "ai_engine.db"):
        self._db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Crée les tables si elles n'existent pas (auto-migration simple)."""
        # CREATE TABLE IF NOT EXISTS pour chaque entité
        # Chaque row stocke le JSON sérialisé du Pydantic model
        # + colonnes indexées pour les queries fréquentes (id, slug, agent_id, etc.)
        ...

    def save_agent(self, agent: Agent) -> Agent:
        agent.updated_at = datetime.now()
        data = agent.model_dump_json()
        # UPSERT (INSERT OR REPLACE)
        self._execute(
            "INSERT OR REPLACE INTO agents (id, slug, data) VALUES (?, ?, ?)",
            (agent.id, agent.slug, data),
        )
        return agent
```

---

## 7. Phase 3 — Services (logique métier pure)

### 7.1 Objectif
Extraire et adapter `llm.py`, `agents.py`, `graph_runtime.py`, `utils.py` en services purs.

### 7.2 LLM Factory

**Pattern conservé** : Le registry pattern avec `@_register` est excellent — on le garde tel quel.

**Changement clé** : Les builders reçoivent un `LLMProviderConfig` (Pydantic) au lieu d'un `Provider` (Django).

```python
# services/llm/factory.py

_BUILDERS: dict[str, Callable[[LLMProviderConfig], BaseChatModel]] = {}

def register_provider(provider_type: str):
    """Décorateur pour enregistrer un builder."""
    def decorator(fn):
        _BUILDERS[provider_type] = fn
        return fn
    return decorator

def create_llm(provider: LLMProviderConfig) -> BaseChatModel:
    """Factory — retourne un ChatModel depuis un LLMProviderConfig Pydantic."""
    builder = _BUILDERS.get(provider.provider_type)
    if not builder:
        raise UnsupportedProviderError(provider.provider_type, available_providers())
    return builder(provider)

def create_llm_for_agent(agent: Agent, storage: StorageBackend) -> BaseChatModel:
    """Factory — résout le provider d'un agent et crée le LLM."""
    provider = storage.get_provider(agent.provider_id)
    if not provider:
        raise ProviderNotFoundError(agent.provider_id)
    # Appliquer les overrides de l'agent
    merged = _merge_config(provider, agent.config)
    return create_llm(merged)
```

**Builders** — Fichiers séparés, même logique :

```python
# services/llm/openai.py
from ai_engine.services.llm.factory import register_provider

@register_provider("openai")
@register_provider("codex")
def build_openai(provider: LLMProviderConfig) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=provider.default_model,
        api_key=provider.api_key.get_secret_value() if provider.api_key else None,
        temperature=provider.settings.temperature,
        max_tokens=provider.settings.max_tokens,
        max_retries=provider.settings.max_retries,
        **({"base_url": provider.api_base_url} if provider.api_base_url else {}),
    )
```

### 7.3 Agent Service

**Changement majeur** : Plus de `Agent.objects.get()` — tout passe par `StorageBackend`.

```python
# services/agent_service.py

class AgentService:
    def __init__(
        self,
        storage: StorageBackend,
        llm_factory: Callable | None = None,
        tool_registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
    ):
        self._storage = storage
        self._llm_factory = llm_factory or create_llm_for_agent
        self._tools = tool_registry or ToolRegistry()
        self._events = event_bus or EventBus()

    def create_agent(
        self,
        agent_slug: str,
        checkpointer=None,
        use_langgraph: bool = True,
    ):
        """Factory — crée un agent LangGraph depuis le storage."""
        agent = self._storage.get_agent_by_slug(agent_slug)
        if not agent:
            raise AgentNotFoundError(agent_slug)
        if not agent.is_active:
            raise AgentDisabledError(agent_slug)

        llm = self._llm_factory(agent, self._storage)
        tools = self._load_tools(agent)
        ...

    async def chat(
        self,
        agent_id: str,
        user_message: str,
        conversation_id: str | None = None,
        owner_id: str | None = None,
    ) -> Message:
        """Envoie un message et gère la boucle tool-calling."""
        ...
```

### 7.4 Graph Runtime

**Changement** : Même logique que `graph_runtime.py` Django, mais via storage :

```python
# services/graph_runtime.py

class GraphRuntime:
    def __init__(self, storage: StorageBackend, agent_service: AgentService):
        self._storage = storage
        self._agent_service = agent_service

    def build_supervisor(self, supervisor_slug: str = "supervisor", checkpointer=None):
        """Construit un LangGraph Supervisor depuis le storage."""
        supervisor = self._storage.get_agent_by_slug(supervisor_slug)
        if not supervisor:
            raise AgentNotFoundError(supervisor_slug)

        agents = self._build_worker_agents(checkpointer)
        supervisor_llm = self._agent_service._llm_factory(supervisor, self._storage)
        ...
```

### 7.5 Execution Tracker (nouveau)

**Nouveau service** qui centralise le tracking (remplace les champs `usage_count`, `total_tokens` sur les models Django) :

```python
# services/execution_tracker.py

class ExecutionTracker:
    """Suit les exécutions, tokens consommés, coûts."""

    def __init__(self, storage: StorageBackend, event_bus: EventBus | None = None):
        self._storage = storage
        self._events = event_bus or EventBus()

    def start_execution(self, agent_id: str, input_data: dict, graph_id: str | None = None) -> Execution: ...
    def add_step(self, execution_id: str, step_type: StepType, input_data: dict, ...) -> ExecutionStep: ...
    def complete_execution(self, execution_id: str, output_data: dict) -> Execution: ...
    def fail_execution(self, execution_id: str, error: str) -> Execution: ...
    def get_usage_stats(self, agent_id: str) -> dict: ...
```

---

## 8. Phase 4 — Tools, Skills & Events

### 8.1 Tools

**Conservation du pattern `function_path`** avec chargement dynamique :

```python
# tools/registry.py

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None: ...
    def register_from_definition(self, definition: ToolDefinition) -> None:
        """Charge un tool depuis un ToolDefinition (ex: depuis le storage)."""
        if definition.function_path:
            func = self._import_function(definition.function_path)
            # Wrapper en Tool compatible
            ...

    def load_for_agent(self, agent: Agent, storage: StorageBackend) -> list[Tool]:
        """Charge tous les tools d'un agent."""
        definitions = storage.list_tools_for_agent(agent.id)
        return [self._resolve(d) for d in definitions if d.is_active]

    @staticmethod
    def _import_function(dotted_path: str):
        """Import dynamique — identique à utils._import_function."""
        module_name, func_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, func_name)
```

**Décorateur `@tool`** standalone (compatible mais pas dépendant de LangChain) :

```python
# tools/decorators.py

def tool(name: str | None = None, description: str | None = None):
    """Décorateur pour transformer une fonction en Tool."""
    def decorator(func):
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        # Introspection des paramètres pour générer le JSON Schema
        ...
        return ToolWrapper(func, tool_name, tool_desc, schema)
    return decorator
```

### 8.2 Skills

**Conservation de `SkillRegistry`** et `BaseSkill` ABC, sans dépendance Django :

```python
# skills/base.py

class BaseSkill(ABC):
    name: str
    description: str
    category: SkillCategory
    required_tool_keys: list[str] = []

    @abstractmethod
    async def execute(self, input_data: dict, context: SkillContext) -> SkillResult: ...

class SkillContext:
    """Contexte d'exécution d'un skill (remplace RunnableConfig + Django request)."""
    llm: BaseChatModel
    tools: list[Tool]
    storage: StorageBackend
    owner_id: str | None = None
    metadata: dict = Field(default_factory=dict)
```

### 8.3 EventBus

**Remplace `django.dispatch.Signal`** :

```python
# events/bus.py

class EventBus:
    def on(self, event: str, callback: Callable) -> None: ...
    def off(self, event: str, callback: Callable) -> None: ...
    def emit(self, event: str, data: dict | None = None) -> None: ...

# events/events.py — Événements prédéfinis

AGENT_CREATED = "agent.created"
AGENT_UPDATED = "agent.updated"
CONVERSATION_STARTED = "conversation.started"
MESSAGE_RECEIVED = "message.received"
MESSAGE_COMPLETED = "message.completed"
TOOL_CALLED = "tool.called"
TOOL_COMPLETED = "tool.completed"
EXECUTION_STARTED = "execution.started"
EXECUTION_COMPLETED = "execution.completed"
EXECUTION_FAILED = "execution.failed"
```

---

## 9. Phase 5 — Adapters (Django, FastAPI)

### 9.1 Django Adapter

**Objectif** : Retrouver **100% du fonctionnel Django actuel** via un adapter qui utilise `ai_engine` sous le capot.

```python
# adapters/django/storage.py

class DjangoORMStorage(StorageBackend):
    """Implémente StorageBackend en utilisant l'ORM Django."""

    def get_agent(self, agent_id: str) -> Agent | None:
        from ai_engine_django.models import AgentModel  # Django model
        try:
            obj = AgentModel.objects.get(id=agent_id)
            return self._to_pydantic(obj)
        except AgentModel.DoesNotExist:
            return None

    def _to_pydantic(self, obj: AgentModel) -> Agent:
        """Convertit un Django model en Pydantic model."""
        return Agent(
            id=str(obj.id),
            name=obj.name,
            slug=obj.slug,
            role=obj.role,
            provider_id=str(obj.provider_id),
            system_prompt=obj.system_prompt,
            tool_ids=[str(t.id) for t in obj.tools.all()],
            ...
        )
```

```python
# adapters/django/views.py — Reconnecte les views DRF

from ai_engine import AgentService
from ai_engine.adapters.django.storage import DjangoORMStorage

storage = DjangoORMStorage()
service = AgentService(storage=storage)

class ChatView(APIView):
    async def post(self, request):
        response = await service.chat(
            agent_id=request.data["agent_id"],
            user_message=request.data["message"],
            owner_id=str(request.user.id),
        )
        return Response({"content": response.content})
```

### 9.2 FastAPI Adapter

```python
# adapters/fastapi/router.py

from fastapi import APIRouter, Depends
from ai_engine import AgentService

router = APIRouter(prefix="/ai", tags=["AI Engine"])

def get_service() -> AgentService:
    """Dependency injection — configuré au startup de l'app."""
    return _service_instance

@router.post("/chat/{agent_id}")
async def chat(agent_id: str, message: str, service: AgentService = Depends(get_service)):
    response = await service.chat(agent_id=agent_id, user_message=message)
    return {"content": response.content, "conversation_id": response.conversation_id}
```

---

## 10. Phase 6 — Tests & Packaging

### 10.1 Stratégie de tests

| Type | Scope | Storage | Priorité |
|---|---|---|---|
| Unit tests | Models, validation, serialization | Aucun | P0 |
| Unit tests | Services (mocked LLM) | `InMemoryStorage` | P0 |
| Unit tests | ToolRegistry, EventBus | Aucun | P0 |
| Integration tests | SQLiteStorage CRUD complet | `SQLiteStorage` | P1 |
| Integration tests | Conversation complète (mock LLM) | `InMemoryStorage` | P1 |
| Integration tests | Multi-agent graph | `InMemoryStorage` | P2 |
| Adapter tests | DjangoORMStorage | Django test DB | P2 |
| Adapter tests | FastAPI router | TestClient | P2 |

### 10.2 Fixtures partagées (`conftest.py`)

```python
@pytest.fixture
def storage():
    return InMemoryStorage()

@pytest.fixture
def sample_provider():
    return LLMProviderConfig(name="test-openai", provider_type=ProviderType.OPENAI, default_model="gpt-4o")

@pytest.fixture
def sample_agent(sample_provider, storage):
    storage.save_provider(sample_provider)
    agent = Agent(name="Test Agent", slug="test-agent", provider_id=sample_provider.id)
    return storage.save_agent(agent)

@pytest.fixture
def mock_llm():
    """LLM mocké qui retourne des réponses prédéfinies."""
    ...
```

### 10.3 `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ai-engine"
version = "0.1.0"
description = "Standalone Python AI agent orchestration engine"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0,<3.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
langchain = [
    "langchain-core>=0.3",
    "langgraph>=0.2",
]
openai = ["langchain-openai>=0.2"]
anthropic = ["langchain-anthropic>=0.2"]
ollama = ["langchain-ollama>=0.2"]
sqlite = ["aiosqlite>=0.19"]
sqlalchemy = ["sqlalchemy[asyncio]>=2.0", "asyncpg>=0.29"]
embeddings = ["sentence-transformers>=2.0"]
all = ["ai-engine[langchain,openai,anthropic,ollama,sqlite]"]
django = ["django>=4.2", "djangorestframework>=3.14"]
fastapi = ["fastapi>=0.110", "uvicorn>=0.27"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.3",
    "mypy>=1.8",
]

[tool.hatch.build.targets.wheel]
packages = ["src/ai_engine"]
```

---

## 11. Conventions & Règles

### 11.1 Conventions de code

| Règle | Détail |
|---|---|
| **Python** | >= 3.11, type hints partout, `from __future__ import annotations` |
| **Models** | Pydantic v2 `BaseModel`, pas de dataclass |
| **IDs** | `str` (UUID4 par défaut), jamais `int` |
| **Timestamps** | `datetime` natif Python, pas de timezone-aware par défaut |
| **Enums** | `class Xxx(str, Enum)` pour serialization JSON transparente |
| **Async** | Services supportent sync ET async (`def` + `async def`) |
| **Imports** | Lazy imports pour les dépendances optionnelles (LangChain, etc.) |
| **Errors** | Exceptions typées dans `exceptions.py`, jamais de `Exception` nu |
| **Logging** | `logging.getLogger(__name__)` dans chaque module |
| **Config** | Variables d'env (`AI_ENGINE_*`) + Pydantic Settings |
| **Tests** | pytest, `InMemoryStorage` par défaut, pas de DB requise |

### 11.2 Règles d'architecture

```
✅ AUTORISÉ :
- ai_engine.services → importe ai_engine.models
- ai_engine.services → importe ai_engine.storage.base (interface)
- ai_engine.storage.sqlite → importe ai_engine.models
- ai_engine.adapters.django → importe tout ai_engine.*

❌ INTERDIT :
- ai_engine.models → N'importe RIEN d'autre (couche la plus basse)
- ai_engine.services → N'importe PAS ai_engine.adapters
- ai_engine.storage.base → N'importe PAS de storage concret
- ai_engine.* (hors adapters/) → N'importe PAS django, fastapi, etc.
```

### 11.3 Gestion des dépendances optionnelles

```python
# Pattern standard pour les imports optionnels

def _check_langchain():
    try:
        import langchain_core
    except ImportError:
        raise ImportError(
            "LangChain is required for this feature. "
            "Install it with: pip install ai-engine[langchain]"
        )

# Utilisé dans services/llm/openai.py :
def build_openai(provider):
    _check_langchain()
    from langchain_openai import ChatOpenAI
    ...
```

---

## 12. Exemples d'utilisation finale

### 12.1 Script Python (3 lignes)

```python
import asyncio
from ai_engine import Agent, AgentService, InMemoryStorage, LLMProviderConfig, ProviderType
from ai_engine.services.llm.openai import OpenAIClient

async def main():
    storage = InMemoryStorage()
    provider = LLMProviderConfig(
        name="openai", provider_type=ProviderType.OPENAI,
        default_model="gpt-4o", api_key="sk-..."
    )
    storage.save_provider(provider)

    agent = Agent(name="Advisor", slug="advisor", provider_id=provider.id,
                  system_prompt="Tu es un conseiller financier expert.")
    storage.save_agent(agent)

    service = AgentService(storage=storage)
    response = await service.chat(agent_id=agent.id, user_message="Analyse le marché")
    print(response.content)

asyncio.run(main())
```

### 12.2 Jupyter Notebook

```python
from ai_engine import Agent, AgentService, InMemoryStorage, LLMProviderConfig

storage = InMemoryStorage()
# ... setup provider & agent ...
service = AgentService(storage=storage)

# Async natif dans Jupyter
response = await service.chat(agent_id=agent.id, user_message="Analyse ce portefeuille")
response.content
```

### 12.3 Avec persistence SQLite

```python
from ai_engine import AgentService
from ai_engine.storage.sqlite import SQLiteStorage

# Tout est persisté dans un fichier
storage = SQLiteStorage("./my_agents.db")
service = AgentService(storage=storage)

# Les agents et conversations survivent entre les exécutions
response = await service.chat(
    agent_id="existing-agent-id",
    conversation_id="existing-conversation-id",
    user_message="Continue notre discussion",
)
```

### 12.4 Avec tools custom

```python
from ai_engine.tools.decorators import tool
from ai_engine import AgentService, ToolRegistry

@tool(name="get_stock_price", description="Get current stock price")
async def get_stock_price(symbol: str) -> str:
    # ... appel API ...
    return f"AAPL: $195.23"

registry = ToolRegistry()
registry.register(get_stock_price)

service = AgentService(storage=storage, tool_registry=registry)
```

### 12.5 Multi-agent graph

```python
from ai_engine import AgentService, GraphRuntime

service = AgentService(storage=storage)
runtime = GraphRuntime(storage=storage, agent_service=service)

# Le supervisor route les requêtes vers les agents spécialisés
app = runtime.build_supervisor(supervisor_slug="supervisor")
result = app.invoke(
    {"messages": [HumanMessage(content="Analyse complète du marché crypto")]},
    config={"configurable": {"thread_id": "thread-42"}},
)
```

### 12.6 Événements / Hooks

```python
from ai_engine import EventBus
from ai_engine.events.events import MESSAGE_COMPLETED, EXECUTION_FAILED

bus = EventBus()

def on_message(data):
    print(f"Message terminé: {data['message_id']}")

def on_error(data):
    alert_team(f"Erreur agent {data['agent_id']}: {data['error']}")

bus.on(MESSAGE_COMPLETED, on_message)
bus.on(EXECUTION_FAILED, on_error)

service = AgentService(storage=storage, event_bus=bus)
```

---

## 13. Risques & Mitigations

| # | Risque | Impact | Probabilité | Mitigation |
|---|--------|--------|-------------|------------|
| 1 | **Sur-engineering** — Trop d'abstractions pour un usage simple | Moyen | Moyenne | Garder l'API publique simple (façade `__init__.py`). Les abstractions sont internes. |
| 2 | **Performance SQLite** — Pas de connection pooling natif | Faible | Basse | SQLite est parfait pour CLI/scripts. Pour la prod, utiliser SQLAlchemy. |
| 3 | **Compatibilité LangChain** — Breaking changes fréquents | Moyen | Haute | Isoler LangChain dans `services/llm/`. Si LangChain change, seuls ces fichiers bougent. |
| 4 | **Adapter Django trop coûteux** — Mapping ORM ↔ Pydantic | Moyen | Moyenne | Commencer avec un mapping simple. Optimiser (bulk queries) si besoin. |
| 5 | **Tests d'intégration LLM** — Appels API coûteux | Faible | Haute | Mocker systématiquement les LLM dans les tests. Tests LLM réels uniquement en CI/nightly. |
| 6 | **Migration données existantes** — DB Django → nouveau schema | Haut | Moyenne | Script de migration dédié. L'adapter Django lit les données existantes. |
| 7 | **Scope creep** — Trop de features dans le package | Moyen | Haute | MVP strict : Models + Storage + AgentService + LLM Factory. Le reste est Phase 2+. |

---

## 14. Checklist de validation

### Phase 1 — Models ✅

- [ ] Tous les Pydantic models compilent et passent `mypy --strict`
- [ ] Chaque model a un test de création, validation, serialization JSON
- [ ] Les Enums couvrent tous les `TextChoices` Django
- [ ] `model_dump()` et `model_validate()` fonctionnent pour chaque model
- [ ] Aucun import Django dans `src/ai_engine/`

### Phase 2 — Storage ✅

- [ ] `InMemoryStorage` implémente **100%** de `StorageBackend`
- [ ] `SQLiteStorage` implémente **100%** de `StorageBackend`
- [ ] Tests CRUD pour chaque entité sur chaque backend
- [ ] `StorageBackend` peut être passé en paramètre à tous les services

### Phase 3 — Services ✅

- [ ] `AgentService.chat()` fonctionne avec `InMemoryStorage` + mock LLM
- [ ] `GraphRuntime.build_supervisor()` fonctionne
- [ ] `ExecutionTracker` trace correctement tokens et coûts
- [ ] LLM Factory supporte au minimum : `openai`, `anthropic`, `ollama`
- [ ] Aucun `Agent.objects.get()` dans le code

### Phase 4 — Tools/Skills/Events ✅

- [ ] `ToolRegistry` charge des tools depuis `ToolDefinition.function_path`
- [ ] `@tool` decorator fonctionne
- [ ] `EventBus` émet et reçoit correctement
- [ ] `BaseSkill` ABC est implémenté par au moins 1 skill concret

### Phase 5 — Adapters ✅

- [ ] `DjangoORMStorage` passe les mêmes tests que `InMemoryStorage`
- [ ] Les views DRF fonctionnent via l'adapter
- [ ] FastAPI router fonctionne avec `Depends()`
- [ ] L'admin Django affiche les données via l'adapter

### Phase 6 — Package ✅

- [ ] `pip install ai-engine` fonctionne
- [ ] `pip install ai-engine[openai]` fonctionne
- [ ] `pip install ai-engine[django]` fonctionne
- [ ] Tous les exemples `examples/*.py` fonctionnent
- [ ] Coverage > 85%
- [ ] README complet avec quickstart
- [ ] `CHANGELOG.md` à jour

---

## Annexe A — Commandes utiles

```bash
# Créer le package
mkdir -p ai_engine/src/ai_engine/{models,services/llm,storage,tools,skills,embeddings,events,adapters/{django,fastapi}}
touch ai_engine/src/ai_engine/__init__.py

# Installer en mode dev
cd ai_engine && pip install -e ".[dev,openai]"

# Lancer les tests
pytest tests/ -v --cov=ai_engine

# Type checking
mypy src/ai_engine --strict

# Linting
ruff check src/ai_engine

# Build
python -m build

# Publish (test PyPI)
twine upload --repository testpypi dist/*
```

## Annexe B — Correspondance fichiers Django → Standalone

| Fichier Django (`django-ai-app/`) | Fichier Standalone (`ai_engine/`) | Action |
|---|---|---|
| `models/provider.py` | `models/provider.py` | **Convertir** Django → Pydantic |
| `models/agent.py` | `models/agent.py` | **Convertir** |
| `models/tool.py` | `models/tool.py` | **Convertir** |
| `models/skill.py` | `models/skill.py` | **Convertir** |
| `models/graph.py` | `models/graph.py` | **Convertir** + éclater `definition` JSON |
| `models/execution.py` | `models/execution.py` | **Convertir** |
| `models/message.py` | `models/message.py` + `models/conversation.py` | **Convertir** + séparer Conversation |
| `models/memory.py` | `models/memory.py` | **Convertir** |
| `models/knowledge.py` | `models/knowledge.py` | **Convertir** |
| `llm.py` | `services/llm/factory.py` + `services/llm/*.py` | **Refactorer** en fichiers séparés |
| `agents.py` | `services/agent_service.py` | **Refactorer** (storage au lieu d'ORM) |
| `graph_runtime.py` | `services/graph_runtime.py` | **Refactorer** |
| `utils.py` | Intégré dans `services/` et `tools/` | **Éclater** |
| `tools/base.py` | `tools/base.py` + `tools/registry.py` | **Refactorer** (sans RunnableConfig) |
| `tools/*.py` | `tools/*.py` | **Copier** (adapter imports) |
| `skills/base.py` | `skills/base.py` | **Copier** (retirer imports Django) |
| `skills/*.py` | `skills/*.py` | **Copier** (adapter imports) |
| `views.py` | `adapters/django/views.py` | **Déplacer** dans adapter |
| `admin.py` | `adapters/django/admin.py` | **Déplacer** dans adapter |
| `urls.py` | `adapters/django/urls.py` | **Déplacer** dans adapter |
| `permissions.py` | `adapters/django/permissions.py` | **Déplacer** dans adapter |
| `apps.py` | `adapters/django/apps.py` | **Déplacer** dans adapter |
| `migrations/` | `adapters/django/migrations/` | **Déplacer** dans adapter |

---

*Document généré le 12 mars 2026 — Version 1.0*
*Prochaine étape : **Phase 1 — Création de la structure et des Models Pydantic***
