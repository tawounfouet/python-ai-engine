# 05 — Configuration, Types et Gestion des Erreurs

---

## 5.1 Configuration — `config.py`

Le package utilise **Pydantic Settings** pour centraliser toute la configuration.
Les paramètres peuvent venir de trois sources (par ordre de priorité) :
1. Variables d'environnement
2. Fichier `.env` à la racine du projet
3. Valeurs par défaut définies dans la classe

### Classe `Settings`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AI_ENGINE_",   # toutes les vars commencent par AI_ENGINE_
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",            # variables inconnues ignorées silencieusement
    )
```

### Paramètres disponibles

| Variable d'env | Champ Python | Défaut | Description |
|---|---|---|---|
| `AI_ENGINE_DEBUG` | `debug` | `False` | Mode debug |
| `AI_ENGINE_LOG_LEVEL` | `log_level` | `"INFO"` | Niveau de log |
| `AI_ENGINE_DEFAULT_PROVIDER_TYPE` | `default_provider_type` | `"openai"` | Provider par défaut |
| `AI_ENGINE_DEFAULT_MODEL` | `default_model` | `"gpt-4o"` | Modèle par défaut |
| `AI_ENGINE_OPENAI_API_KEY` | `openai_api_key` | `""` | Clé API OpenAI globale |
| `AI_ENGINE_ANTHROPIC_API_KEY` | `anthropic_api_key` | `""` | Clé API Anthropic globale |
| `AI_ENGINE_DEFAULT_STORAGE` | `default_storage` | `"memory"` | Backend de stockage |
| `AI_ENGINE_SQLITE_DB_PATH` | `sqlite_db_path` | `"ai_engine.db"` | Chemin fichier SQLite |
| `AI_ENGINE_JSON_STORAGE_PATH` | `json_storage_path` | `"ai_engine_data/"` | Dossier JSON storage |
| `AI_ENGINE_MAX_TOOL_ITERATIONS` | `max_tool_iterations` | `10` | Max boucles tool |
| `AI_ENGINE_DEFAULT_TEMPERATURE` | `default_temperature` | `0.7` | Température d'inférence |
| `AI_ENGINE_DEFAULT_MAX_TOKENS` | `default_max_tokens` | `4096` | Max tokens par réponse |
| `AI_ENGINE_DEFAULT_TIMEOUT` | `default_timeout` | `30` | Timeout en secondes |

### Singleton via `lru_cache`

```python
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance singleton des settings."""
    return Settings()
```

L'instance est créée **une seule fois** (lazy) par processus. Pour les tests nécessitant
des settings différents, un reset du cache est requis :

```python
get_settings.cache_clear()
```

### Usage

```python
from ai_engine.config import get_settings

settings = get_settings()
print(settings.default_model)    # "gpt-4o"
print(settings.debug)            # False
```

---

## 5.2 Types partagés — `types.py`

Ce module centralise tous les `StrEnum` du domaine. Son rôle est **purement déclaratif** :
aucune logique métier.

### Pourquoi `StrEnum` ?

`StrEnum` (Python 3.11+) fait hériter l'enum de `str` :

```python
class ProviderType(StrEnum):
    OPENAI = "openai"

# Comparaison directe avec les strings JSON
assert ProviderType.OPENAI == "openai"     # True
json.dumps({"type": ProviderType.OPENAI})  # '{"type": "openai"}' (pas besoin de .value)
```

Cela simplifie énormément la sérialisation JSON et les comparaisons dans les filtres
de stockage.

### Enums et leurs usages

**`ProviderType`** — Types de providers LLM supportés (définition, pas forcément implémentés) :

```
Famille OpenAI  : OPENAI, OPENAI_AZURE, CODEX
Famille Anthropic : ANTHROPIC, CLAUDE_CODE
LLMs Chinois    : QWEN, MOONSHOT, KIMI_CODING, GLM, MINIMAX, XIAOMI
Gateways        : OPENROUTER, VERCEL_AI
Cloud           : BEDROCK, VERTEX_AI
Spécialisés     : VENICE, ZAI, OPENCODE_ZEN
Local           : OLLAMA, LLAMACPP, VLLM
Générique       : CUSTOM
```

> Note : Seuls `OPENAI`, `ANTHROPIC` et `OLLAMA` ont des clients implémentés dans la Phase 3.
> `GROQ` et `GEMINI` ont des fichiers clients mais ne figurent pas encore dans `ProviderType`.

**Enums métier** décrits dans [02-couche-modeles.md](02-couche-modeles.md).

---

## 5.3 Hiérarchie des exceptions — `exceptions.py`

**Règle fondamentale :** Jamais de `raise Exception(...)` nu dans le code.
Toutes les exceptions héritent de `AIEngineError`.

### Arbre d'héritage

```
AIEngineError (base)
│
├── ProviderError
│   ├── LLMError                  ← erreur lors d'un appel LLM
│   ├── ProviderNotFoundError     ← provider_id inconnu
│   ├── UnsupportedProviderError  ← provider_type non supporté
│   └── APIKeyMissingError        ← clé API absente
│
├── AgentError
│   ├── AgentNotFoundError        ← agent_id inconnu
│   └── AgentDisabledError        ← agent inactif (is_active=False)
│
├── ConversationError
│   └── ConversationNotFoundError ← conversation_id inconnue
│
├── GraphError
│   └── GraphNotFoundError        ← graph_id inconnu
│
├── ExecutionError
│   └── ExecutionNotFoundError    ← execution_id inconnue
│
├── ToolError
│   ├── ToolNotFoundError         ← tool_id ou tool_key inconnu
│   └── ToolExecutionError        ← erreur pendant l'exécution du tool
│
├── StorageError
│   └── StorageConnectionError    ← impossible de se connecter au storage
│
└── MissingDependencyError        ← dépendance optionnelle non installée
```

### Exceptions informatives avec contexte

Chaque exception "not found" stocke l'identifiant concerné pour faciliter le débogage :

```python
class AgentNotFoundError(AgentError):
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' not found.")

class APIKeyMissingError(ProviderError):
    def __init__(self, provider_name: str, env_var: str | None = None) -> None:
        self.provider_name = provider_name
        self.env_var = env_var
        msg = f"API key missing for provider '{provider_name}'."
        if env_var:
            msg += f" Set it via environment variable '{env_var}'."
        super().__init__(msg)
```

### `MissingDependencyError` — Guide d'installation automatique

Cette exception est levée quand une dépendance optionnelle est absente. Elle inclut
automatiquement la commande d'installation :

```python
raise MissingDependencyError(package="openai", extra="openai")
# → "Package 'openai' is required for this feature.
#    Install it with: pip install ai-engine[openai]"
```

### Usage dans les tests

```python
import pytest
from ai_engine.exceptions import AgentNotFoundError

def test_get_agent_not_found(service):
    with pytest.raises(AgentNotFoundError) as exc_info:
        service.get_agent("nonexistent-id")
    assert exc_info.value.agent_id == "nonexistent-id"
```

---

## 5.4 API publique — `__init__.py`

La façade publique expose une **API stable et complète** pour les consommateurs du package.
Tout import doit pouvoir se faire depuis `ai_engine` directement :

```python
# Import unique — jamais besoin d'aller dans les sous-modules
from ai_engine import (
    # Modèles
    Agent, AgentConfig, AgentRole,
    Conversation, ConversationStatus,
    Execution, ExecutionStep, ExecutionStatus,
    Graph, GraphNode, GraphEdge, GraphStatus, NodeType,
    LLMProviderConfig, ProviderType,
    Message, MessageRole, ToolCall, ToolResult, TokenUsage,
    ToolDefinition, ToolType,
    Skill, SkillCategory, AgentSkillAssignment, Proficiency,
    AgentMemory, MemoryType,
    KnowledgeSource,

    # Configuration
    Settings, get_settings,

    # Exceptions
    AIEngineError,
    AgentError, AgentNotFoundError, AgentDisabledError,
    ConversationError, ConversationNotFoundError,
    ProviderError, ProviderNotFoundError, UnsupportedProviderError, APIKeyMissingError,
    LLMError,
    StorageError, StorageConnectionError,
    ToolError, ToolNotFoundError, ToolExecutionError,
    ExecutionError, ExecutionNotFoundError,
    GraphError, GraphNotFoundError,
    MissingDependencyError,
)
```

Les services et le storage s'importent depuis leurs sous-modules :

```python
from ai_engine.services import AgentService, get_llm_client
from ai_engine.storage import StorageBackend, InMemoryStorage, SQLiteStorage
```

---

## 5.5 Typage statique et qualité du code

### mypy (strict mode)

Le fichier `pyproject.toml` configure mypy en mode strict :

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]
```

Le plugin `pydantic.mypy` permet à mypy de comprendre les types générés par Pydantic
(notamment les validators et les champs optionnels).

### Ruff — Linting et Formatage

Remplace flake8, isort et black dans un seul outil :

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]
```

Règles activées : erreurs de style (`E`), pyflakes (`F`), imports (`I`), nommage (`N`),
warnings (`W`), modernisation (`UP`), bugs potentiels (`B`), simplifications (`SIM`),
optimisations de type checking (`TCH`).

### `py.typed` — Marqueur PEP 561

La présence du fichier `src/ai_engine/py.typed` (vide) indique aux outils
(mypy, pyright, IDE) que ce package est entièrement annoté et supporte la vérification
de types en tant que dépendance.

### Exceptions à `TCH` pour le storage

```toml
[tool.ruff.lint.per-file-ignores]
"src/ai_engine/storage/memory.py" = ["TCH"]
"src/ai_engine/storage/sqlite.py" = ["TCH"]
"tests/**" = ["TCH"]
```

Les backends de storage utilisent les types modèles à **l'exécution** (pour `model_validate_json`,
les comparaisons de type dans les filtres), donc les imports ne doivent pas être déplacés
dans des blocs `TYPE_CHECKING`. De même, les tests ont besoin de tous leurs imports à l'exécution.
