# 02 — Couche Modèles (Domaine)

La couche modèles définit l'ensemble des **entités métier** du package. Toutes sont des
`pydantic.BaseModel` purs — aucune dépendance framework, aucune logique de persistence.

---

## 2.1 Vue d'ensemble des entités

```
┌────────────────────┐     ┌────────────────────┐
│  LLMProviderConfig │     │     AgentConfig     │
│  ─────────────────│     │  ─────────────────  │
│  id (UUID)        │     │  max_iterations     │
│  name             │◄────│  max_tokens_per_run │
│  provider_type    │     │  temperature        │
│  default_model    │     │  enable_memory      │
│  api_key (Secret) │     │  enable_tools       │
│  capabilities     │     │  enable_rag         │
│  pricing          │     └────────────────────┘
│  settings         │              │ embedded dans
└─────────┬──────────┘              ▼
          │ référencé par   ┌────────────────────┐
          │ provider_id     │       Agent        │
          └────────────────►│  ─────────────────│
                            │  id (UUID)         │
                            │  name / slug       │
                            │  role (AgentRole)  │
                            │  provider_id       │
                            │  system_prompt     │
                            │  tool_ids: list    │
                            │  skill_ids: list   │
                            │  knowledge_ids     │
                            │  config: AgentConfig│
                            └──────────┬─────────┘
                                       │ agent_id
          ┌────────────────────────────┼────────────────────────┐
          ▼                            ▼                        ▼
┌──────────────────┐      ┌──────────────────────┐   ┌────────────────────┐
│  Conversation    │      │      Execution       │   │    AgentMemory     │
│  ───────────────│      │  ────────────────────│   │  ─────────────────│
│  id              │      │  id                  │   │  id                │
│  agent_id        │      │  agent_id            │   │  agent_id          │
│  owner_id        │      │  graph_id?           │   │  key               │
│  status          │      │  conversation_id?    │   │  content           │
│  message_count   │      │  status              │   │  memory_type       │
│  total_tokens    │      │  input_data          │   │  embedding?        │
└──────────┬───────┘      │  output_data         │   │  relevance_score   │
           │ conv_id      │  token_usage         │   │  expires_at?       │
           ▼              │  steps: list         │   └────────────────────┘
┌──────────────────┐      └──────────────────────┘
│    Message       │
│  ───────────────│
│  id              │
│  conversation_id │
│  role (enum)     │
│  content         │
│  tool_calls      │
│  tool_result?    │
│  token_usage?    │
└──────────────────┘
```

---

## 2.2 Détail des entités

### `LLMProviderConfig` — `models/provider.py`

Configuration d'un fournisseur LLM. Équivalent standalone du modèle Django `Provider`.

**Sous-modèles embarqués :**

| Sous-modèle | Rôle |
|---|---|
| `ProviderCapabilities` | `vision`, `function_calling`, `streaming`, `context_window` |
| `PricingConfig` | Tarification au token (`input_per_1k_tokens`, `output_per_1k_tokens`) |
| `ProviderSettings` | Paramètres d'inférence par défaut (`temperature`, `max_tokens`, `top_p`, ...) |

**Sécurité :** L'API key est de type `pydantic.SecretStr` — elle ne s'affiche jamais dans les
logs/repr. L'accès à la valeur brute passe obligatoirement par `get_api_key_value()`.

```python
# Ne logue JAMAIS la clé directement
provider = LLMProviderConfig(api_key="sk-...")
print(provider.api_key)            # SecretStr('**********')
print(provider.get_api_key_value()) # "sk-..."  ← accès explicite requis
```

---

### `Agent` + `AgentConfig` — `models/agent.py`

Représente un acteur intelligent. Les relations vers Tools, Skills et KnowledgeSources
sont des **listes d'IDs** (pas de jointure ORM) :

```python
agent = Agent(
    name="Research Assistant",
    role=AgentRole.RESEARCHER,
    provider_id="<uuid-provider>",
    tool_ids=["<uuid-web-search>", "<uuid-summarize>"],
    skill_ids=["<uuid-research-skill>"],
    knowledge_base_ids=["<uuid-docs>"],
    config=AgentConfig(
        max_iterations=20,
        enable_rag=True,
        temperature=0.3,        # override du provider
    ),
)
```

`AgentConfig` porte la configuration comportementale de l'agent. En particulier :
- `temperature: float | None` — si `None`, utilise la valeur du provider
- `enable_memory / enable_tools / enable_rag` — feature flags
- `retry_on_failure` + `max_retries` — résilience

---

### `Conversation` — `models/conversation.py`

Sépare le concept de **session de chat** de l'exécution technique.
- Porte les compteurs dénormalisés `message_count` et `total_tokens` (perf)
- Le champ `summary` permet de stocker un résumé condensé de la conversation
  pour la gestion du contexte long-terme
- `status` : `ACTIVE` / `ARCHIVED` / `DELETED`

---

### `Message` — `models/message.py`

Message dans une conversation. Le JSONField opaque du modèle Django est **éclaté en
sous-modèles typés** :

| Champ | Type | Django original |
|---|---|---|
| `tool_calls` | `list[ToolCall]` | `metadata["tool_calls"]` |
| `tool_result` | `ToolResult \| None` | `metadata["tool_result"]` |
| `token_usage` | `TokenUsage \| None` | `metadata["usage"]` |

**`ToolCall`** — Compatible avec le format OpenAI function calling :
```python
ToolCall(
    id="call_abc123",
    name="web_search",
    arguments={"query": "quantum computing 2025"},
)
```

**`ToolResult`** — Réponse à un appel de fonction :
```python
ToolResult(
    tool_call_id="call_abc123",
    output="Quantum computing advances...",
    is_error=False,
)
```

**`TokenUsage`** — Métriques au niveau message :
```python
TokenUsage(
    prompt_tokens=150,
    completion_tokens=300,
    total_tokens=450,
    estimated_cost_usd=0.0045,
)
```

**Rôles possibles** (`MessageRole`) : `system`, `user`, `assistant`, `tool`

---

### `Execution` + `ExecutionStep` — `models/execution.py`

Trace une exécution complète d'un agent.

- `Execution` = session globale (statut, input/output final, métriques agrégées)
- `ExecutionStep` = chaque étape atomique (appel LLM, appel de tool, résultat, décision)

```
Execution (RUNNING)
├── ExecutionStep (LLM_CALL, order=1)    ← appel GPT-4o
├── ExecutionStep (TOOL_CALL, order=2)   ← appel web_search
├── ExecutionStep (TOOL_RESULT, order=3) ← résultat web_search
└── ExecutionStep (LLM_CALL, order=4)    ← synthèse finale
```

Chaque step a son propre chronomètre (`duration_ms`) et son coût (`cost`).

---

### `ToolDefinition` — `models/tool.py`

Définit une fonction/outil appelable par un Agent. Important : c'est une **définition**,
pas une implémentation. L'implémentation est référencée via `function_path`.

```python
tool = ToolDefinition(
    key="web_search",          # identifiant unique technique
    name="Web Search",
    tool_type=ToolType.API,
    parameters_schema={        # JSON Schema format OpenAI function calling
        "type": "object",
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
    },
    function_path="myapp.tools.web_search.execute",
    requires_approval=False,
    is_dangerous=False,
)
```

La méthode `get_function_schema()` retourne le format exact attendu par l'API OpenAI
pour le function calling.

**Types** (`ToolType`) : `FUNCTION`, `API`, `DATABASE`, `FILE`, `CONNECTOR`, `CUSTOM`

---

### `Skill` + `AgentSkillAssignment` — `models/skill.py`

Distinction fondamentale :
- **`ToolDefinition`** = fonction atomique (API call, DB query, file read)
- **`Skill`** = capacité de haut niveau combinant plusieurs tools + raisonnement

```
ResearchSkill = web_search + summarize + fact_check + system_prompt spécialisé
CodingSkill   = generate_code + run_tests + code_review + système_prompt spécialisé
```

`AgentSkillAssignment` représente la **table de liaison** entre un Agent et un Skill,
avec en plus un niveau de maîtrise (`Proficiency` : `BASIC`, `INTERMEDIATE`, `ADVANCED`, `EXPERT`)
et un override de provider optionnel.

---

### `AgentMemory` — `models/memory.py`

Mémoire persistante d'un Agent entre les exécutions.

| Type (`MemoryType`) | Usage |
|---|---|
| `SHORT_TERM` | Contexte de la session courante (expire via `expires_at`) |
| `LONG_TERM` | Connaissances acquises (persist jusqu'à suppression explicite) |
| `EPISODIC` | Souvenirs d'exécutions passées (indexés pour recherche sémantique) |

Le champ `embedding: list[float] | None` permet la recherche sémantique via
produit scalaire si un modèle d'embedding est disponible.

---

### `Graph` + `GraphNode` + `GraphEdge` — `models/graph.py`

Décrit un **workflow multi-agents** style LangGraph. Le JSONField opaque de Django
est remplacé par des types forts :

```python
graph = Graph(
    name="Research Pipeline",
    agent_id="<uuid>",
    entry_node_id="start",
    nodes=[
        GraphNode(node_id="start", node_type=NodeType.INPUT),
        GraphNode(node_id="researcher", node_type=NodeType.AGENT,
                  config={"agent_id": "<uuid>"}),
        GraphNode(node_id="reviewer", node_type=NodeType.AGENT,
                  config={"agent_id": "<uuid>"}),
        GraphNode(node_id="end", node_type=NodeType.OUTPUT),
    ],
    edges=[
        GraphEdge(source_node_id="start", target_node_id="researcher"),
        GraphEdge(source_node_id="researcher", target_node_id="reviewer",
                  condition="state['score'] > 0.8"),
        GraphEdge(source_node_id="reviewer", target_node_id="end"),
    ],
)
```

**Types de nœuds** (`NodeType`) : `AGENT`, `CONDITION`, `TOOL`, `INPUT`, `OUTPUT`, `PARALLEL`, `LOOP`

Les champs `position_x` / `position_y` sur `GraphNode` sont réservés aux éditeurs visuels futurs.

---

### `KnowledgeSource` + `Document` + `Chunk` — `models/knowledge.py`

Pipeline RAG (Retrieval-Augmented Generation) :

```
KnowledgeSource (PDF, URL, texte brut)
    └── Document (document parsé)
            └── Chunk (fragment avec embedding)
```

- `KnowledgeSource` : remplace le `FileField` Django par `file_path: str | None`
- `Document` : agrège les morceaux d'un fichier (après parsing)
- `Chunk` : fragment prêt pour la recherche sémantique (embedding pré-calculé)

**Types de sources** (`SourceType`) : `DOCUMENT`, `URL`, `TEXT`, `DATABASE`, `API`

---

## 2.3 Types partagés — `types.py`

Tous les `StrEnum` du domaine sont centralisés dans `types.py` (aucune logique métier,
uniquement des définitions) :

| Enum | Valeurs principales |
|---|---|
| `ProviderType` | `OPENAI`, `ANTHROPIC`, `OLLAMA`, `GROQ`, `BEDROCK`, `VERTEX_AI`, `CUSTOM`, ... |
| `AgentRole` | `ASSISTANT`, `RESEARCHER`, `CODER`, `ANALYST`, `REVIEWER`, `ORCHESTRATOR` |
| `ToolType` | `FUNCTION`, `API`, `DATABASE`, `FILE`, `CONNECTOR` |
| `SkillCategory` | `RESEARCH`, `CODING`, `COMMUNICATION`, `DATA`, `CREATIVE`, `AUTOMATION` |
| `Proficiency` | `BASIC`, `INTERMEDIATE`, `ADVANCED`, `EXPERT` |
| `MessageRole` | `SYSTEM`, `USER`, `ASSISTANT`, `TOOL` |
| `ConversationStatus` | `ACTIVE`, `ARCHIVED`, `DELETED` |
| `GraphStatus` | `DRAFT`, `ACTIVE`, `ARCHIVED` |
| `NodeType` | `AGENT`, `CONDITION`, `TOOL`, `INPUT`, `OUTPUT`, `PARALLEL`, `LOOP` |
| `ExecutionStatus` | `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED` |
| `StepType` | `LLM_CALL`, `TOOL_CALL`, `TOOL_RESULT`, `DECISION`, `ERROR` |
| `MemoryType` | `SHORT_TERM`, `LONG_TERM`, `EPISODIC` |
| `SourceType` | `DOCUMENT`, `URL`, `TEXT`, `DATABASE`, `API` |
| `IndexStatus` | `PENDING`, `INDEXED`, `FAILED` |

L'utilisation de `StrEnum` (Python 3.11+) permet la sérialisation directe en JSON
sans conversion — `"openai"` au lieu de `<ProviderType.OPENAI: 'openai'>`.

---

## 2.4 API publique des modèles — `__init__.py`

La façade publique du package exporte directement les modèles les plus utilisés :

```python
from ai_engine import (
    # Modèles
    Agent, AgentConfig,
    Conversation,
    Execution, ExecutionStep,
    LLMProviderConfig,
    Message, ToolCall, ToolResult, TokenUsage,
    ToolDefinition,
    Skill, AgentSkillAssignment,
    Graph, GraphNode, GraphEdge,
    AgentMemory,
    KnowledgeSource,

    # Types
    ProviderType, AgentRole, ToolType, MessageRole,
    ExecutionStatus, ConversationStatus, ...

    # Config
    Settings, get_settings,

    # Exceptions
    AgentNotFoundError, ProviderError, ...
)
```
