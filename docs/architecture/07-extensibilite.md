# 07 — Extensibilité et Phases Futures

Ce document décrit les **points d'extension** du package et les phases de développement
planifiées, telles qu'elles ressortent de l'analyse du code et de la documentation.

---

## 7.1 Points d'extension actuels

### Ajouter un nouveau provider LLM

1. Créer un nouveau fichier `src/ai_engine/services/llm/myprovider.py` :

```python
from ai_engine.services.llm.base import LLMClient, LLMRequest, LLMResponse, StreamChunk
from ai_engine.models.provider import LLMProviderConfig

class MyProviderClient(LLMClient):

    def __init__(self, provider_config: LLMProviderConfig) -> None:
        super().__init__(provider_config)
        api_key = provider_config.get_api_key_value()
        # ... init du SDK provider

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.validate_capabilities(request)
        # ... appel SDK + conversion en LLMResponse

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        ...

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        ...

    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        ...
```

2. Ajouter le `ProviderType` correspondant dans `types.py` (si absent)

3. Enregistrer dans `services/llm/factory.py` :

```python
elif provider_config.provider_type == ProviderType.MY_PROVIDER:
    from ai_engine.services.llm.myprovider import MyProviderClient
    return MyProviderClient(provider_config)
```

4. Ajouter l'extra optionnel dans `pyproject.toml` si le SDK est une dépendance :

```toml
[project.optional-dependencies]
myprovider = ["myprovider-sdk>=1.0"]
```

### Ajouter un nouveau backend de stockage

Créer `src/ai_engine/storage/mybackend.py` qui hérite de `StorageBackend` et implémente
l'intégralité des méthodes abstraites. Par exemple, pour un stockage PostgreSQL via asyncpg :

```python
from ai_engine.storage.base import StorageBackend

class PostgreSQLStorage(StorageBackend):
    def __init__(self, connection_string: str) -> None:
        ...

    def save_agent(self, agent: Agent) -> Agent:
        ...

    # ... toutes les méthodes abstraites
```

Enregistrer dans `storage/__init__.py` :

```python
from ai_engine.storage.mybackend import PostgreSQLStorage
__all__ = [..., "PostgreSQLStorage"]
```

Aucune modification du code service n'est nécessaire.

---

## 7.2 Phase 4 — Système de Tools et Function Calling

*Planifiée, non encore implémentée*

Cette phase ajoutera un **registry de tools** et un runtime d'exécution automatique.

Structure cible :
```
src/ai_engine/
└── tools/
    ├── __init__.py
    ├── base.py          ← Tool (ABC), ToolResult
    ├── registry.py      ← ToolRegistry (enregistrement + lookup)
    ├── executor.py      ← ToolExecutor (exécution + error handling)
    └── builtins/
        ├── web_search.py
        ├── calculator.py
        └── code_runner.py
```

**`ToolRegistry`** permettrait d'associer le `function_path` d'une `ToolDefinition` à
sa fonction Python réelle :

```python
registry = ToolRegistry()
registry.register("web_search", my_web_search_function)

executor = ToolExecutor(registry)
result = executor.call(tool_call)  # ToolCall → ToolResult
```

L'`AgentService` pourrait alors automatiser la boucle tool-calling :
```
LLM → tool_calls → executor → ToolResult → LLM → tool_calls → ... → réponse finale
```

---

## 7.3 Phase 5 — Bus d'événements

*Planifiée, non encore implémentée*

Un `EventBus` permettrait aux composants de communiquer de façon découplée :

```
src/ai_engine/
└── events/
    ├── __init__.py
    ├── bus.py       ← EventBus (subscribe/publish)
    └── events.py    ← AgentCreated, MessageSent, ExecutionCompleted, ...
```

Usage prévu :
```python
bus = EventBus()
bus.subscribe("execution.completed", lambda e: send_webhook(e))
bus.subscribe("message.received", lambda e: update_metrics(e))

# Dans AgentService.chat() :
bus.publish(MessageSentEvent(agent_id=..., conv_id=..., tokens=70))
```

---

## 7.4 Phase 6 — Graph Runtime Multi-Agents

*Planifiée, non encore implémentée*

Permettra d'exécuter les workflows décrits par le modèle `Graph` avec LangGraph :

```
src/ai_engine/services/
└── graph_runtime.py   ← GraphRuntime (compile + execute)
```

Fonctionnalités attendues :
- **Compilation** : `Graph` (Pydantic) → `CompiledStateGraph` (LangGraph)
- **Exécution** : routing conditionnel basé sur les `GraphEdge.condition`
- **Supervisor Pattern** : un agent orchestrateur délègue aux agents spécialisés
- **Checkpointing** : sauvegarde de l'état du graph dans le storage
- **Parallélisme** : exécution simultanée des nœuds `NodeType.PARALLEL`

```python
runtime = GraphRuntime(storage, tool_registry)
result = runtime.execute(
    graph_id="<uuid>",
    input_data={"task": "Research quantum computing trends"},
)
```

---

## 7.5 Phase 7 — Adapters Framework

*Planifiée, non encore implémentée*

### Adapter Django

```
src/ai_engine/adapters/django/
├── __init__.py
├── models.py        ← Django ORM proxy models (thin wrapper)
├── storage.py       ← DjangoORMStorage (implements StorageBackend)
├── admin.py         ← Interface d'administration auto-générée
├── serializers.py   ← DRF serializers pour les modèles Pydantic
├── views.py         ← DRF viewsets (REST API)
└── signals.py       ← Django signals → EventBus bridge
```

`DjangoORMStorage` implémenterait `StorageBackend` en utilisant l'ORM Django,
permettant d'utiliser `ai-engine` dans un projet Django existant sans
changer la moindre ligne de code dans les services.

### Adapter FastAPI

```
src/ai_engine/adapters/fastapi/
├── __init__.py
├── router.py        ← FastAPI router (APIRouter)
├── dependencies.py  ← Dependency injection (Depends)
└── schemas.py       ← Pydantic response/request schemas
```

---

## 7.6 Décisions d'architecture notables

### Choix de Pydantic v2 (pas LangChain Models)

LangChain fournit ses propres types (`BaseMessage`, `HumanMessage`, `AIMessage`).
Le package a délibérément choisi de ne **pas** les utiliser comme modèles de domaine
pour rester indépendant de LangChain.

Conséquence : chaque implémentation de `LLMClient` convertit entre le format
interne (`Message`) et le format provider (OpenAI, Anthropic, etc.).

### Choix UUID string vs UUID type

Les IDs sont des `str` contenant des UUID v4, pas le type Python `uuid.UUID`.
Cela simplifie la sérialisation JSON, la comparaison et le stockage SQL.

### Pas de relations directes entre entités

Le choix délibéré de références par ID (au lieu d'objets imbriqués ou de jointures)
permet :
- La **sérialisation simple** : pas de recursion infinie
- Le **stockage indépendant** : chaque entité dans sa propre table/dict
- La **scalabilité** : pas de "lazy loading" problématique entre couches

Le verso est que le code applicatif doit parfois charger plusieurs entités séparément.

### `TYPE_CHECKING` pour les imports circulaires

Le fichier `storage/base.py` utilise le bloc `TYPE_CHECKING` pour éviter les imports
circulaires tout en bénéficiant des annotations de type :

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ai_engine.models.agent import Agent
    # ... autres imports utilisés uniquement pour les annotations
```

Cela signifie que ces imports ne sont évalués qu'à l'analyse statique (mypy, pyright),
pas à l'exécution — d'où les exceptions `TCH` dans la config Ruff pour les backends
de stockage qui utilisent ces types à l'exécution.

---

## 7.7 Résumé de l'état d'avancement

| Phase | Description | Statut |
|---|---|---|
| Phase 1 | Structure + Modèles Pydantic | ✅ Terminée |
| Phase 2 | Storage Layer | ✅ Terminée |
| Phase 3 | Services + LLM Clients | ✅ Terminée |
| Phase 4 | Tool System & Function Calling | 🔲 Planifiée |
| Phase 5 | Event Bus & Workflows | 🔲 Planifiée |
| Phase 6 | Graph Runtime Multi-Agents | 🔲 Planifiée |
| Phase 7 | Adapters Django & FastAPI | 🔲 Planifiée |

### Couverture de tests actuelle

- **36/36 tests** passent (Phase 3 validée)
- Tests unitaires : `tests/unit/models/` (1 fichier par modèle)
- Tests unitaires services : `tests/unit/services/`
- Tests unitaires storage : `tests/unit/storage/`
- Tests d'intégration : `tests/integration/`
- Fixtures partagées : `tests/conftest.py` (providers, agents, tools, messages, graphs...)

### Lacunes identifiées pour les phases futures

1. **Pas de tests pour les clients LLM** (nécessite des mocks API)
2. **Groq et Gemini non enregistrés dans la factory** (fichiers présents mais non branchés)
3. **Pas d'implémentation async** pour `StorageBackend` (tout est synchrone)
4. **Pas de gestion de migration** pour `SQLiteStorage` (schema uniquement `CREATE IF NOT EXISTS`)
5. **Pas d'implémentation du cycle tool-calling** dans `AgentService.chat()`
