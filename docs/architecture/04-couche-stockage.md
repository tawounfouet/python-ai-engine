# 04 — Couche Stockage

La couche stockage implémente le pattern **Port & Adapter** (ou Repository Pattern) :
`StorageBackend` est le port (interface abstraite), et chaque implémentation concrète
(`InMemoryStorage`, `SQLiteStorage`) est un adapter.

---

## 4.1 Interface abstraite — `StorageBackend`

`StorageBackend` est une classe abstraite (`ABC`) qui définit le **contrat complet de
persistence**. Toute implémentation doit couvrir les 10 entités du domaine.

### Opérations couvertes

Pour **chaque entité**, l'interface définit :

| Pattern | Exemple (pour Agent) |
|---|---|
| `save_*(entity)` | `save_agent(agent)` → upsert (create ou update) |
| `get_*(id)` | `get_agent(agent_id)` → `Agent \| None` |
| `get_*_by_slug(slug)` | `get_agent_by_slug(slug)` → `Agent \| None` |
| `list_*(**filters)` | `list_agents(owner_id=..., role=..., is_active=...)` |
| `delete_*(id)` | `delete_agent(agent_id)` → `bool` |

### Entités couvertes

| Entité | Méthodes spécifiques |
|---|---|
| `LLMProviderConfig` | `get_provider_by_name()` |
| `Agent` | `get_agent_by_slug()`, `list_agents(owner_id, role, is_active)` |
| `ToolDefinition` | `get_tool_by_key()`, `list_tools_for_agent(agent_id)` |
| `Skill` | `save_skill_assignment()`, `list_skill_assignments_for_agent()` |
| `Conversation` | `list_conversations(agent_id, owner_id)` |
| `Message` | `get_messages(conversation_id, limit, offset)` |
| `Execution` | `list_executions(agent_id, status)`, `get_execution_steps()` |
| `Graph` | `get_graph_by_slug()`, `list_graphs_for_agent()` |
| `AgentMemory` | `get_memory(agent_id, key)`, `list_memories(agent_id, memory_type)`, `delete_expired_memories()` |
| `KnowledgeSource` | `list_knowledge_sources_for_agent()` |

### Context Manager

```python
@contextmanager
def transaction(self) -> Iterator[None]:
    """Gestionnaire de contexte pour les transactions."""
    ...
```

Permet aux implémentations avancées de grouper des opérations atomiques.

---

## 4.2 `InMemoryStorage` — `storage/memory.py`

Implémentation en mémoire utilisant des **dictionnaires Python**. Parfaite pour les tests
unitaires et le prototypage rapide.

### Structure interne

```python
class InMemoryStorage(StorageBackend):
    def __init__(self):
        self._providers: dict[str, LLMProviderConfig] = {}
        self._agents: dict[str, Agent] = {}
        self._tools: dict[str, ToolDefinition] = {}
        self._skills: dict[str, Skill] = {}
        self._skill_assignments: dict[str, AgentSkillAssignment] = {}
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, Message] = {}
        self._executions: dict[str, Execution] = {}
        self._execution_steps: dict[str, ExecutionStep] = {}
        self._graphs: dict[str, Graph] = {}
        self._memories: dict[str, AgentMemory] = {}
        self._knowledge_sources: dict[str, KnowledgeSource] = {}
```

### Comportements notables

- `save_*()` : met à jour `updated_at` avant de stocker
- Toutes les requêtes sont des itérations sur les dicts → O(n) pour les listes filtrées
- `list_tools_for_agent(agent_id)` : résout `agent.tool_ids` en objets ToolDefinition
- `delete_expired_memories()` : filtre sur `memory.is_expired` (propriété calculée)
- **Aucune persistence** — les données disparaissent à la fin du processus

### Usage recommandé

```python
# Tests unitaires (via conftest.py)
@pytest.fixture
def storage():
    return InMemoryStorage()

# Prototypage rapide
storage = InMemoryStorage()
service = AgentService(storage)
```

---

## 4.3 `SQLiteStorage` — `storage/sqlite.py`

Implémentation SQLite sans dépendances ORM. Stratégie hybride :
> **JSON sérialisé** dans une colonne `data` + **colonnes indexées** pour les filtres fréquents

### Philosophie de la stratégie

Au lieu d'un schéma relationnel classique (une colonne par champ), chaque entité
est stockée comme un JSON complet dans la colonne `data`, avec seulement quelques
colonnes extraites pour les index :

```sql
CREATE TABLE agents (
    id      TEXT PRIMARY KEY,
    slug    TEXT NOT NULL DEFAULT '',    ← indexé (filtres slug)
    owner_id TEXT,                       ← indexé (filtres par owner)
    role    TEXT NOT NULL DEFAULT 'assistant', ← indexé (filtres par rôle)
    is_active INTEGER NOT NULL DEFAULT 1,
    data    TEXT NOT NULL                ← JSON complet Pydantic
);
CREATE INDEX idx_agents_slug  ON agents (slug);
CREATE INDEX idx_agents_owner ON agents (owner_id);
```

**Avantages :**
- **Schéma évolutif** : ajouter des champs au modèle Pydantic ne nécessite pas de migration
- **Requêtes simples** : lookup par ID/slug très rapides via les index
- **Cohérence** : la source de vérité est le JSON Pydantic, pas le schéma SQL

**Inconvénients :**
- Pas de requêtes complexes sur les champs internes du JSON (sans JSON_EXTRACT)
- Pas de contraintes d'intégrité référentielle

### Tables créées

| Table | Colonnes indexées |
|---|---|
| `providers` | `name`, `is_active` |
| `agents` | `slug`, `owner_id`, `role`, `is_active` |
| `tools` | `key`, `is_active` |
| `skills` | `is_active` |
| `skill_assignments` | `agent_id`, `skill_id` |
| `conversations` | `agent_id`, `owner_id`, `status` |
| `messages` | `conversation_id`, `role`, `created_at` |
| `executions` | `agent_id`, `conversation_id`, `status`, `graph_id` |
| `execution_steps` | `execution_id`, `step_type` |
| `graphs` | `slug`, `agent_id`, `owner_id`, `status` |
| `memories` | `agent_id`, `key`, `memory_type`, `expires_at` |
| `knowledge_sources` | `source_type`, `index_status` |

### Sérialisation/Désérialisation

```python
def _serialize(model) -> str:
    """JSON string depuis un modèle Pydantic."""
    return model.model_dump_json()

# Désérialisation — exemple pour Agent:
agent = Agent.model_validate_json(row["data"])
```

Le format `SecretStr` de `LLMProviderConfig.api_key` est correctement sérialisé/désérialisé
grâce à `model_dump_json()` qui gère les types Pydantic spéciaux.

### Configuration SQLite

```python
self._conn.execute("PRAGMA journal_mode=WAL")    # meilleure concurrence lecture/écriture
self._conn.execute("PRAGMA foreign_keys=ON")     # intégrité référentielle (si utilisée)
```

### Context Manager

```python
def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()   # ferme la connexion SQLite

# Usage :
with SQLiteStorage("agents.db") as storage:
    storage.save_agent(agent)
```

### Mode mémoire pour les tests

```python
# Pas de fichier sur le disque — utile pour les tests sans InMemoryStorage
storage = SQLiteStorage(":memory:")
```

---

## 4.4 Comparaison des implémentations

| Critère | InMemoryStorage | SQLiteStorage |
|---|---|---|
| Persistence | ❌ Aucune (RAM) | ✅ Fichier sur disque |
| Setup | `InMemoryStorage()` | `SQLiteStorage("file.db")` |
| Performance | O(n) scan | Index SQL sur colonnes clés |
| Migrations | ❌ N/A | ✅ `CREATE IF NOT EXISTS` auto |
| Dépendances | Aucune | `sqlite3` (stdlib Python) |
| Multi-process | ❌ Non | ✅ WAL mode |
| Tests | ✅ Idéal | ✅ `":memory:"` |
| Production | ❌ Non | ✅ Scripts/CLI/notebooks |
| Scalabilité | Limité par la RAM | Limité par SQLite |

---

## 4.5 Implémentations futures

Le code source et la documentation anticipent les implémentations suivantes (non encore
développées) :

| Implémentation | Extra pip | Usage prévu |
|---|---|---|
| `JSONFileStorage` | stdlib | Debug, export, échange de données |
| `SQLAlchemyStorage` | `[sqlalchemy]` | PostgreSQL, MySQL pour les projets scalables |
| `DjangoORMStorage` | adapter Django | Intégration dans des projets Django existants |

Ces implémentations devront respecter exactement le contrat `StorageBackend` — aucun
changement de code dans les services ne sera nécessaire.

---

## 4.6 Pattern dans les tests

```python
# conftest.py — fixture de storage partagée
@pytest.fixture
def storage():
    return InMemoryStorage()

# test_agent_service.py
def test_create_agent(storage):
    service = AgentService(storage)
    provider = LLMProviderConfig(name="test", ...)
    storage.save_provider(provider)

    agent = service.create_agent(
        name="Test",
        provider_id=provider.id,
    )
    assert storage.get_agent(agent.id) is not None
```

L'injection de dépendance permet de remplacer `SQLiteStorage` par `InMemoryStorage`
dans les tests sans modifier une seule ligne de code des services.
