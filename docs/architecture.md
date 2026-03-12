# Architecture du Module Django AI (`django-ai-app`)

Ce document décrit l'architecture technique de l'application `django-ai-app`, un composant modulaire permettant de centraliser et d'orchestrer la création et l'exécution d'agents intelligents propulsés par des LLMs, via **LangChain** et **LangGraph**.

## 1. Vue d'ensemble

Le module est construit sur un principe de configuration pilotée par la base de données (Database-Driven AI). Contrairement aux implémentations où les agents et providers sont codés en dur, `django-ai-app` stocke la configuration des LLMs (Providers), le comportement des Agents (Prompts, Tools, Skills) et l'orchestration (Graphs) sous forme de modèles Django.

L'application agit ensuite comme une **Factory Dynamique** qui instancie à la volée les bons objets (_ChatModels_ LangChain, _Agents_ LangGraph) prêts à être exécutés ou orchestrés.

### Diagramme simplifié
`Modèles DB (Provider, Agent, Tool)` -> `Factories (llm.py, agents.py)` -> `Runtime (LangChain / LangGraph)` -> `Exécution`

---

## 2. Modèles de Données Principaux (Models)

### `Provider` (`models/provider.py`)
Gère les connexions aux backends LLM (OpenAI, Anthropic, Ollama, Bedrock, etc.).
- Stocke les configurations génériques (`config`) et les informations sensibles (`secrets` comme `api_key`).
- Offre une abstraction sur le type de backend utilisé.

### `Agent` (`models/agent.py`)
Représente un acteur intelligent.
- **Rôle** : Définit sa spécialité (`assistant`, `researcher`, `coder`, `orchestrator`, etc.).
- **Relations** : Attaché à un `Provider`, dispose d'une liste de `Tools` et de `Skills`.
- **Personnalisation** : Contient le `system_prompt` et permet de surcharger (override) la configuration du provider (ex: température spécifique à l'agent).

### `Graph` (`models/graph.py`)
Représente un workflow multi-étapes.
- Décrit la définition d'un graphe d'états (nodes, edges, state) pour structurer des processus complexes ou custom via JSON.

### `Tool` et `Skill`
Décrivent les capacités des agents. Les _Tools_ sont des fonctions spécifiques que l'agent peut appeler (ex: recherche web, interrogation BDD), tandis que les _Skills_ sont des groupements logiques de capacités.

---

## 3. Composants Core (Core Components)

### `LLM Factory` (`llm.py`)
Instancie des `BaseChatModel` de LangChain à partir du modèle `Provider`.
- **Registre dynamique** : Utilise le décorateur `@_register("type")` pour associer un type de provider à une fonction builder.
- **Sécurité** : Résout les clés API en priorisant le champ `secrets` de la DB, avec un fallback sécurisé sur les variables d'environnement.
- Prend en charge de multiples environnements (Azure, OpenAI, vLLM, Vertex, etc.) de manière unifiée.

### `Agent Factory` (`agents.py`)
Crée des exécuteurs LangChain (`AgentExecutor`) ou LangGraph (`CompiledStateGraph`) depuis la table `Agent`.
- Charge le `system_prompt`, instancie le LLM (via `llm.py`), et injecte les Tools associés.
- Gère la mémoire d'exécution en associant un `checkpointer` (ex: `MemorySaver`).

### `Graph Runtime & Supervisor` (`graph_runtime.py`)
Gère l'orchestration "Multi-Agent" en utilisant le design pattern Supervisor (Superviseur) porté par `langgraph-supervisor`.
- `build_supervisor()` : Récupère l'agent défini comme `orchestrator` en base de données, ainsi que la liste des agents spécialisés.
- Crée un routeur intelligent où le LLM Superviseur délègue dynamiquement les requêtes complexes aux agents spécialisés appropriés (ex: router une question technique au `coder`, puis envoyer la réponse au `reviewer`).
- Peut éventuellement construire des workflows 100% personnalisés basés sur le modèle `Graph.definition`.

---

## 4. Extensibilité & Ajout de Nouveaux Types

### Ajouter un nouveau backend LLM
1. Définir une fonction `_build_nouveau_backend()` dans `llm.py`.
2. Utiliser le décorateur `@_register("nouveau_backend")` au-dessus de la fonction.
3. Instancier la classe LangChain correspondante (en résolvant les clés API) et la retourner.

### Ajouter une compétence ou un outil
1. Créer le script de l'outil dans le dossier `tools/` ou `skills/` en utilisant les primitives LangChain (ex: `@tool`).
2. Créer une entrée dans la base de données (`Tool` ou `Skill`) pour le rendre assignable aux `Agents`.

---

## Conclusion
L'architecture de `django-ai-app` offre une scalabilité et une flexibilité remarquables. En repoussant la configuration des IA au niveau Base de Données, elle permet aux administrateurs de créer, ajuster et orchestrer de nouveaux agents (et d'expérimenter de nouveaux Providers) depuis l'interface d'administration Django, le tout uniformisé par la robustesse des écosystèmes LangChain et LangGraph en arrière-plan.



```sh
┌─────────────────────────────────────────────────────────┐
│              Consumers (interchangeables)                │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ ┌───────────────┐  │
│  │ Django  │ │ FastAPI │ │ Script │ │ Jupyter Notebook│ │
│  │ adapter │ │ adapter │ │  CLI   │ │               │  │
│  └────┬────┘ └────┬────┘ └───┬────┘ └──────┬────────┘  │
│       └───────────┴──────────┴─────────────┘            │
│                        │                                │
│  ┌─────────────────────▼──────────────────────────────┐ │
│  │          ai_engine (Pure Python Package)            │ │
│  │                                                    │ │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │ │
│  │  │  Models  │  │ Services │  │  Graph Runtime  │  │ │
│  │  │(Pydantic)│→ │  (Pure)  │→ │    (Pure)       │  │ │
│  │  └──────────┘  └──────────┘  └─────────────────┘  │ │
│  │       │                                            │ │
│  │  ┌────▼─────────────────────────────────────────┐  │ │
│  │  │         Storage Interface (ABC)              │  │ │
│  │  │  ┌──────────┐ ┌────────┐ ┌───────────────┐  │  │ │
│  │  │  │ In-Memory│ │ SQLite │ │ Django ORM    │  │  │ │
│  │  │  └──────────┘ └────────┘ └───────────────┘  │  │ │
│  │  │  ┌──────────┐ ┌────────────────────────┐    │  │ │
│  │  │  │ JSON File│ │ SQLAlchemy (Postgres)  │    │  │ │
│  │  │  └──────────┘ └────────────────────────┘    │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

```sh
ai_engine/
├── src/
│   └── ai_engine/
│       ├── __init__.py                  # API publique
│       ├── config.py                    # Configuration (env vars, fichiers)
│       ├── exceptions.py               # Exceptions métier
│       ├── types.py                     # Types communs, enums
│       │
│       ├── models/                      # Pydantic models (domaine)
│       │   ├── __init__.py
│       │   ├── provider.py              # LLMProvider, ProviderConfig
│       │   ├── agent.py                 # Agent, AgentConfig
│       │   ├── skill.py                 # Skill, SkillParameter
│       │   ├── conversation.py          # Conversation
│       │   ├── message.py               # Message, ToolCall, ToolResult
│       │   ├── knowledge.py             # KnowledgeBase, Document, Chunk
│       │   ├── graph.py                 # Graph, GraphNode, GraphEdge
│       │   └── execution.py             # Execution, TokenUsage, Cost
│       │
│       ├── services/                    # Logique métier pure
│       │   ├── __init__.py
│       │   ├── llm/                     # Abstraction LLM
│       │   │   ├── __init__.py
│       │   │   ├── base.py              # LLMClient (ABC)
│       │   │   ├── openai.py            # OpenAI implementation
│       │   │   ├── anthropic.py         # Anthropic implementation
│       │   │   ├── mistral.py           # Mistral implementation
│       │   │   └── factory.py           # LLMClientFactory
│       │   │
│       │   ├── agent_service.py         # Orchestration agent
│       │   ├── conversation_service.py  # Gestion conversations
│       │   ├── knowledge_service.py     # RAG: ingestion, embedding, retrieval
│       │   ├── graph_runtime.py         # Exécution graphs multi-agents
│       │   └── skill_registry.py        # Enregistrement/résolution skills
│       │
│       ├── storage/                     # Persistence (pluggable)
│       │   ├── __init__.py
│       │   ├── base.py                  # StorageBackend (ABC)
│       │   ├── memory.py               # InMemoryStorage
│       │   ├── sqlite.py               # SQLiteStorage
│       │   ├── json_file.py            # JSONFileStorage
│       │   └── sqlalchemy.py           # SQLAlchemyStorage (PostgreSQL, etc.)
│       │
│       ├── tools/                       # Tools/Functions pour agents
│       │   ├── __init__.py
│       │   ├── base.py                  # Tool (ABC), ToolResult
│       │   ├── registry.py              # ToolRegistry
│       │   ├── web_search.py            # Exemple: recherche web
│       │   ├── calculator.py            # Exemple: calcul
│       │   └── code_executor.py         # Exemple: exécution code
│       │
│       ├── embeddings/                  # Abstraction embeddings
│       │   ├── __init__.py
│       │   ├── base.py                  # EmbeddingClient (ABC)
│       │   ├── openai.py
│       │   └── sentence_transformers.py
│       │
│       ├── events/                      # Système d'événements
│       │   ├── __init__.py
│       │   ├── bus.py                   # EventBus
│       │   └── events.py               # Event definitions
│       │
│       └── adapters/                    # Intégrations framework
│           ├── __init__.py
│           ├── django/
│           │   ├── __init__.py
│           │   ├── models.py            # Django ORM models (proxy)
│           │   ├── storage.py           # DjangoORMStorage
│           │   ├── admin.py             # Admin registration
│           │   ├── serializers.py       # DRF serializers
│           │   ├── views.py             # DRF viewsets
│           │   └── signals.py           # Django signals → EventBus bridge
│           │
│           └── fastapi/
│               ├── __init__.py
│               ├── router.py            # FastAPI router
│               ├── dependencies.py      # Dependency injection
│               └── schemas.py           # Response schemas
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures communes
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_agent_service.py
│   │   ├── test_llm_clients.py
│   │   ├── test_graph_runtime.py
│   │   ├── test_knowledge_service.py
│   │   ├── test_tool_registry.py
│   │   └── test_event_bus.py
│   ├── integration/
│   │   ├── test_sqlite_storage.py
│   │   ├── test_openai_client.py
│   │   └── test_full_conversation.py
│   └── adapters/
│       ├── test_django_storage.py
│       └── test_fastapi_router.py
│
├── examples/
│   ├── 01_basic_chat.py
│   ├── 02_agent_with_tools.py
│   ├── 03_multi_agent_graph.py
│   ├── 04_rag_knowledge_base.py
│   ├── 05_custom_storage.py
│   ├── 06_django_integration.py
│   ├── 07_fastapi_integration.py
│   └── 08_notebook_demo.ipynb
│
├── pyproject.toml
├── README.md
├── LICENSE
└── CHANGELOG.md
```

## 2. Modèles de domaine (Pydantic)
### 2.1 Provider
```python
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, SecretStr, Field
from datetime import datetime
from uuid import uuid4


class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MISTRAL = "mistral"
    GOOGLE = "google"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class LLMProviderConfig(BaseModel):
    """Configuration pour un provider LLM."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    provider_type: ProviderType
    api_key: SecretStr | None = None
    api_base_url: str | None = None
    default_model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    extra_params: dict = Field(default_factory=dict)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True
```

### 2.2 Agent
```python
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class AgentRole(str, Enum):
    ASSISTANT = "assistant"
    ANALYST = "analyst"
    ADVISOR = "advisor"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    CUSTOM = "custom"


class AgentConfig(BaseModel):
    """Configuration comportementale d'un agent."""

    max_turns: int = 50
    max_tokens_per_response: int = 4096
    temperature: float = 0.7
    enable_memory: bool = True
    enable_tools: bool = True
    enable_rag: bool = False
    retry_on_failure: bool = True
    max_retries: int = 3


class Agent(BaseModel):
    """Représentation d'un agent AI."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    role: AgentRole = AgentRole.ASSISTANT
    system_prompt: str = ""
    provider_id: str | None = None
    model: str | None = None
    config: AgentConfig = Field(default_factory=AgentConfig)
    skill_ids: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    # Ownership (framework-agnostic)
    owner_id: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
```

### 2.3 2.3 Conversation & Message

```python
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Appel d'outil par l'assistant."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    arguments: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Résultat d'un appel d'outil."""

    tool_call_id: str
    content: str
    is_error: bool = False


class TokenUsage(BaseModel):
    """Consommation de tokens."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class Message(BaseModel):
    """Un message dans une conversation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    role: MessageRole
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_result: ToolResult | None = None
    token_usage: TokenUsage | None = None
    model_used: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
```

### 2.4 Graph (multi-agent workflows)

```python
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class NodeType(str, Enum):
    AGENT = "agent"
    CONDITION = "condition"
    TOOL = "tool"
    INPUT = "input"
    OUTPUT = "output"
    PARALLEL = "parallel"
    LOOP = "loop"


class GraphEdge(BaseModel):
    """Connexion entre deux nœuds."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_node_id: str
    target_node_id: str
    condition: str | None = None  # Expression conditionnelle optionnelle
    label: str = ""


class GraphNode(BaseModel):
    """Nœud dans un graph multi-agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    node_type: NodeType
    agent_id: str | None = None  # Si type AGENT
    config: dict = Field(default_factory=dict)
    position: dict = Field(default_factory=dict)  # Pour UI: {"x": 0, "y": 0}


class Graph(BaseModel):
    """Workflow multi-agent sous forme de graph."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    entry_node_id: str | None = None
    owner_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```




## 3. Storage Layer (Persistence abstraite)
### 3.1 Interface abstraite
```python

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Generic

from ai_engine.models.agent import Agent
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.message import Message
from ai_engine.models.graph import Graph
from ai_engine.models.knowledge import KnowledgeBase


class StorageBackend(ABC):
    """Interface abstraite pour la persistence des données."""

    # ── Providers ────────────────────────────────────────────

    @abstractmethod
    def save_provider(self, provider: LLMProviderConfig) -> LLMProviderConfig: ...

    @abstractmethod
    def get_provider(self, provider_id: str) -> LLMProviderConfig | None: ...

    @abstractmethod
    def list_providers(self) -> list[LLMProviderConfig]: ...

    @abstractmethod
    def delete_provider(self, provider_id: str) -> bool: ...

    # ── Agents ───────────────────────────────────────────────

    @abstractmethod
    def save_agent(self, agent: Agent) -> Agent: ...

    @abstractmethod
    def get_agent(self, agent_id: str) -> Agent | None: ...

    @abstractmethod
    def list_agents(
        self,
        owner_id: str | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]: ...

    @abstractmethod
    def delete_agent(self, agent_id: str) -> bool: ...

    # ── Conversations ────────────────────────────────────────

    @abstractmethod
    def save_conversation(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Conversation | None: ...

    @abstractmethod
    def list_conversations(
        self,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Conversation]: ...

    @abstractmethod
    def delete_conversation(self, conversation_id: str) -> bool: ...

    # ── Messages ─────────────────────────────────────────────

    @abstractmethod
    def save_message(self, message: Message) -> Message: ...

    @abstractmethod
    def get_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[Message]: ...

    # ── Graphs ───────────────────────────────────────────────

    @abstractmethod
    def save_graph(self, graph: Graph) -> Graph: ...

    @abstractmethod
    def get_graph(self, graph_id: str) -> Graph | None: ...

    @abstractmethod
    def list_graphs(self, owner_id: str | None = None) -> list[Graph]: ...

    @abstractmethod
    def delete_graph(self, graph_id: str) -> bool: ...
```

### 3.2 InMemoryStorage (pour tests & prototypage)

```sh
from __future__ import annotations

from ai_engine.storage.base import StorageBackend
from ai_engine.models.agent import Agent
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.message import Message
from ai_engine.models.graph import Graph


class InMemoryStorage(StorageBackend):
    """Storage en mémoire — parfait pour tests et prototypage."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProviderConfig] = {}
        self._agents: dict[str, Agent] = {}
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[Message]] = {}  # conversation_id → messages
        self._graphs: dict[str, Graph] = {}

    # ── Providers ────────────────────────────────────────────

    def save_provider(self, provider: LLMProviderConfig) -> LLMProviderConfig:
        self._providers[provider.id] = provider
        return provider

    def get_provider(self, provider_id: str) -> LLMProviderConfig | None:
        return self._providers.get(provider_id)

    def list_providers(self) -> list[LLMProviderConfig]:
        return list(self._providers.values())

    def delete_provider(self, provider_id: str) -> bool:
        return self._providers.pop(provider_id, None) is not None

    # ── Agents ───────────────────────────────────────────────

    def save_agent(self, agent: Agent) -> Agent:
        self._agents[agent.id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def list_agents(
        self,
        owner_id: str | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]:
        agents = list(self._agents.values())
        if owner_id is not None:
            agents = [a for a in agents if a.owner_id == owner_id]
        if is_active is not None:
            agents = [a for a in agents if a.is_active == is_active]
        return agents

    def delete_agent(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

    # ── Conversations ────────────────────────────────────────

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self._conversations[conversation.id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self._conversations.get(conversation_id)

    def list_conversations(
        self,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Conversation]:
        convs = list(self._conversations.values())
        if agent_id is not None:
            convs = [c for c in convs if c.agent_id == agent_id]
        if owner_id is not None:
            convs = [c for c in convs if c.owner_id == owner_id]
        return convs

    def delete_conversation(self, conversation_id: str) -> bool:
        self._messages.pop(conversation_id, None)
        return self._conversations.pop(conversation_id, None) is not None

    # ── Messages ─────────────────────────────────────────────

    def save_message(self, message: Message) -> Message:
        if message.conversation_id not in self._messages:
            self._messages[message.conversation_id] = []
        self._messages[message.conversation_id].append(message)
        return message

    def get_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        messages = self._messages.get(conversation_id, [])
        if limit is not None:
            messages = messages[-limit:]
        return messages

    # ── Graphs ───────────────────────────────────────────────

    def save_graph(self, graph: Graph) -> Graph:
        self._graphs[graph.id] = graph
        return graph

    def get_graph(self, graph_id: str) -> Graph | None:
        return self._graphs.get(graph_id)

    def list_graphs(self, owner_id: str | None = None) -> list[Graph]:
        graphs = list(self._graphs.values())
        if owner_id is not None:
            graphs = [g for g in graphs if g.owner_id == owner_id]
        return graphs

    def delete_graph(self, graph_id: str) -> bool:
        return self._graphs.pop(graph_id, None) is not None
```

## 4. Services (logique métier pure)
### 4.1 LLM Client abstrait
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ai_engine.models.message import Message, TokenUsage


@dataclass
class LLMResponse:
    """Réponse d'un appel LLM."""

    content: str
    tool_calls: list[dict] | None = None
    token_usage: TokenUsage | None = None
    model: str = ""
    finish_reason: str = ""
    raw_response: dict | None = None


class LLMClient(ABC):
    """Interface abstraite pour les providers LLM."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse: ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ):
        """Yields LLMResponse chunks."""
        ...

    def messages_to_dicts(self, messages: list[Message]) -> list[dict]:
        """Convertit les Message Pydantic en format dict pour l'API."""
        return [
            {
                "role": m.role.value,
                "content": m.content,
                **({"tool_calls": [tc.model_dump() for tc in m.tool_calls]} if m.tool_calls else {}),
                **({"tool_call_id": m.tool_result.tool_call_id, "content": m.tool_result.content} if m.tool_result else {}),
            }
            for m in messages
        ]
```

### 4.2 Agent Service

```python
from __future__ import annotations

from datetime import datetime

from ai_engine.models.agent import Agent
from ai_engine.models.conversation import Conversation
from ai_engine.models.message import Message, MessageRole, TokenUsage
from ai_engine.services.llm.base import LLMClient
from ai_engine.storage.base import StorageBackend
from ai_engine.tools.registry import ToolRegistry
from ai_engine.events.bus import EventBus


class AgentService:
    """Service principal d'orchestration d'un agent."""

    def __init__(
        self,
        storage: StorageBackend,
        llm_client: LLMClient,
        tool_registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._storage = storage
        self._llm = llm_client
        self._tools = tool_registry or ToolRegistry()
        self._events = event_bus or EventBus()

    async def chat(
        self,
        agent_id: str,
        user_message: str,
        conversation_id: str | None = None,
        owner_id: str | None = None,
    ) -> Message:
        """Envoie un message à un agent et retourne sa réponse."""

        # 1. Récupérer l'agent
        agent = self._storage.get_agent(agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # 2. Récupérer ou créer la conversation
        if conversation_id:
            conversation = self._storage.get_conversation(conversation_id)
            if conversation is None:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = Conversation(
                agent_id=agent_id,
                title=user_message[:100],
                owner_id=owner_id,
            )
            self._storage.save_conversation(conversation)

        # 3. Sauvegarder le message utilisateur
        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message,
        )
        self._storage.save_message(user_msg)

        # 4. Construire le contexte
        history = self._storage.get_messages(conversation.id)
        messages = self._build_messages(agent, history)

        # 5. Préparer les tools
        tools = self._get_tools_schema(agent) if agent.config.enable_tools else None

        # 6. Appeler le LLM
        response = await self._llm.chat(
            messages=messages,
            model=agent.model,
            temperature=agent.config.temperature,
            max_tokens=agent.config.max_tokens_per_response,
            tools=tools,
        )

        # 7. Gérer les tool calls (boucle)
        assistant_msg = await self._handle_response(
            agent, conversation, response, messages, tools
        )

        # 8. Émettre un événement
        self._events.emit("agent.message.completed", {
            "agent_id": agent_id,
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
        })

        return assistant_msg

    def _build_messages(self, agent: Agent, history: list[Message]) -> list[dict]:
        """Construit la liste de messages pour l'API LLM."""
        messages = []

        # System prompt
        if agent.system_prompt:
            messages.append({"role": "system", "content": agent.system_prompt})

        # Historique
        for msg in history:
            messages.append({"role": msg.role.value, "content": msg.content})

        return messages

    def _get_tools_schema(self, agent: Agent) -> list[dict] | None:
        """Retourne le schéma des tools disponibles pour l'agent."""
        if not agent.tool_names:
            return None
        tools = []
        for tool_name in agent.tool_names:
            tool = self._tools.get(tool_name)
            if tool:
                tools.append(tool.schema())
        return tools or None

    async def _handle_response(self, agent, conversation, response, messages, tools):
        """Gère la réponse LLM, y compris les tool calls en boucle."""

        # Tool call loop
        max_iterations = agent.config.max_retries
        iteration = 0

        while response.tool_calls and iteration < max_iterations:
            for tc in response.tool_calls:
                tool = self._tools.get(tc["function"]["name"])
                if tool:
                    result = await tool.execute(**tc["function"]["arguments"])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(result),
                    })

            response = await self._llm.chat(
                messages=messages,
                model=agent.model,
                tools=tools,
            )
            iteration += 1

        # Sauvegarder la réponse finale
        assistant_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            token_usage=response.token_usage,
            model_used=response.model,
        )
        self._storage.save_message(assistant_msg)

        return assistant_msg
```

## 5. Système d'événements
```python

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """Bus d'événements simple — remplace les signals Django."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event_name: str, callback: Callable) -> None:
        """Enregistre un listener pour un événement."""
        self._listeners[event_name].append(callback)

    def off(self, event_name: str, callback: Callable) -> None:
        """Retire un listener."""
        self._listeners[event_name].remove(callback)

    def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Émet un événement à tous les listeners."""
        for callback in self._listeners.get(event_name, []):
            try:
                callback(data or {})
            except Exception as e:
                logger.error(f"Error in event listener for '{event_name}': {e}")

    def clear(self) -> None:
        """Supprime tous les listeners."""
        self._listeners.clear()
```

## 6. Tools
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class ToolParameter(BaseModel):
    name: str
    type: str  # "string", "number", "boolean", etc.
    description: str
    required: bool = True
    enum: list[str] | None = None


class Tool(ABC):
    """Interface abstraite pour un tool."""

    name: str
    description: str
    parameters: list[ToolParameter] = []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Exécute le tool avec les arguments donnés."""
        ...

    def schema(self) -> dict:
        """Retourne le schéma OpenAI-compatible du tool."""
        properties = {}
        required = []
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
```

```sh
from __future__ import annotations

from ai_engine.tools.base import Tool


class ToolRegistry:
    """Registre central des tools disponibles."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def unregister(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None
```

### 7. API Publique (__init__.py)

```python
"""
AI Engine — Standalone Python package for AI agent orchestration.

Usage:
    from ai_engine import Agent, AgentService, InMemoryStorage
    from ai_engine.services.llm.openai import OpenAIClient
"""

__version__ = "0.1.0"

# Models
from ai_engine.models.agent import Agent, AgentConfig, AgentRole
from ai_engine.models.provider import LLMProviderConfig, ProviderType
from ai_engine.models.conversation import Conversation, ConversationStatus
from ai_engine.models.message import Message, MessageRole, TokenUsage, ToolCall, ToolResult
from ai_engine.models.graph import Graph, GraphNode, GraphEdge, NodeType
from ai_engine.models.knowledge import KnowledgeBase

# Services
from ai_engine.services.agent_service import AgentService
from ai_engine.services.graph_runtime import GraphRuntime

# Storage
from ai_engine.storage.base import StorageBackend
from ai_engine.storage.memory import InMemoryStorage

# Tools
from ai_engine.tools.base import Tool, ToolParameter
from ai_engine.tools.registry import ToolRegistry

# Events
from ai_engine.events.bus import EventBus

__all__ = [
    # Models
    "Agent", "AgentConfig", "AgentRole",
    "LLMProviderConfig", "ProviderType",
    "Conversation", "ConversationStatus",
    "Message", "MessageRole", "TokenUsage", "ToolCall", "ToolResult",
    "Graph", "GraphNode", "GraphEdge", "NodeType",
    "KnowledgeBase",
    # Services
    "AgentService", "GraphRuntime",
    # Storage
    "StorageBackend", "InMemoryStorage",
    # Tools
    "Tool", "ToolParameter", "ToolRegistry",
    # Events
    "EventBus",
]
```

### 8. Configuration & Packaging

```sh
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
authors = [
    { name = "Your Name", email = "you@example.com" },
]

dependencies = [
    "pydantic>=2.0,<3.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
openai = ["openai>=1.0"]
anthropic = ["anthropic>=0.30"]
mistral = ["mistralai>=1.0"]
sqlite = ["aiosqlite>=0.19"]
sqlalchemy = ["sqlalchemy>=2.0", "asyncpg>=0.29"]
embeddings = ["sentence-transformers>=2.0"]
all = [
    "ai-engine[openai,anthropic,mistral,sqlite,sqlalchemy,embeddings]",
]
django = ["django>=4.2"]
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

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true
```

## 9. Exemples d'utilisation finale
### 9.1 Script simple

```sh
import asyncio
from ai_engine import Agent, AgentService, InMemoryStorage
from ai_engine.services.llm.openai import OpenAIClient

async def main():
    # Setup
    storage = InMemoryStorage()
    llm = OpenAIClient(api_key="sk-...")

    agent = Agent(
        name="Financial Advisor",
        system_prompt="Tu es un conseiller financier expert.",
        model="gpt-4o",
    )
    storage.save_agent(agent)

    service = AgentService(storage=storage, llm_client=llm)

    # Chat
    response = await service.chat(
        agent_id=agent.id,
        user_message="Analyse les tendances du marché crypto en 2026",
    )
    print(response.content)

asyncio.run(main())
```

### 9.2 Notebook Jupyter
```python
# Dans un notebook — pas de Django, pas de setup complexe
from ai_engine import Agent, AgentService, InMemoryStorage
from ai_engine.services.llm.openai import OpenAIClient

storage = InMemoryStorage()
llm = OpenAIClient(api_key="sk-...")
agent = Agent(name="Analyst", system_prompt="...", model="gpt-4o")
storage.save_agent(agent)
service = AgentService(storage=storage, llm_client=llm)

# Utilisable directement avec await dans Jupyter
response = await service.chat(agent_id=agent.id, user_message="...")
response.content
```

### 9.3 Intégration Django (adapter)
```python
from ai_engine import AgentService
from ai_engine.adapters.django.storage import DjangoORMStorage
from ai_engine.services.llm.openai import OpenAIClient

# Le storage utilise tes models Django existants sous le capot
storage = DjangoORMStorage()
llm = OpenAIClient(api_key=settings.OPENAI_API_KEY)
service = AgentService(storage=storage, llm_client=llm)

# Dans une view
async def chat_view(request, agent_id):
    response = await service.chat(
        agent_id=agent_id,
        user_message=request.data["message"],
        owner_id=str(request.user.id),
    )
    return JsonResponse({"content": response.content})
```

### 9.4 Intégration FastAPI
```python
from fastapi import FastAPI, Depends
from ai_engine import AgentService
from ai_engine.storage.sqlite import SQLiteStorage
from ai_engine.services.llm.openai import OpenAIClient

app = FastAPI()
storage = SQLiteStorage("./agents.db")
llm = OpenAIClient(api_key="sk-...")
service = AgentService(storage=storage, llm_client=llm)

@app.post("/chat/{agent_id}")
async def chat(agent_id: str, message: str):
    response = await service.chat(agent_id=agent_id, user_message=message)
    return {"content": response.content}
```

## 10. Résumé de l'architecture

┌──────────────────────────────────────────────────────────────┐
│                     CONSUMERS                                │
│  Script │ Notebook │ Django │ FastAPI │ CLI │ Lambda │ Tests │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                  ai_engine (Public API)                       │
│  Agent │ AgentService │ Graph │ GraphRuntime │ EventBus      │
└────────────────────────┬─────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Services   │ │    Tools     │ │   Events     │
│  LLM Client  │ │  Registry    │ │    Bus       │
│  Agent Svc   │ │  Tool ABC    │ │  Listeners   │
│  Graph Svc   │ │  Built-ins   │ │              │
│  RAG Svc     │ │              │ │              │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                Storage Interface (ABC)                        │
│  ┌──────────┐ ┌────────┐ ┌───────────┐ ┌─────────────────┐ │
│  │ InMemory │ │ SQLite │ │ JSON File │ │ Django ORM      │ │
│  │ (tests)  │ │ (local)│ │ (proto)   │ │ (adapter)       │ │
│  └──────────┘ └────────┘ └───────────┘ └─────────────────┘ │
│  ┌──────────────────────┐                                    │
│  │ SQLAlchemy (Postgres)│                                    │
│  └──────────────────────┘                                    │
└──────────────────────────────────────────────────────────────┘