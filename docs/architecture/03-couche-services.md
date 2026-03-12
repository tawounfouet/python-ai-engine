# 03 — Couche Services

La couche services orchestre la logique métier en coordinant les modèles, le stockage et
les clients LLM. Elle s'organise en deux sous-systèmes : le **service Agent** (haut niveau)
et les **clients LLM** (interface avec les APIs externes).

---

## 3.1 Vue d'ensemble

```
services/
├── agent.py          ← AgentService : CRUD agents, conversations, chat
└── llm/
    ├── base.py       ← LLMClient (ABC), LLMRequest, LLMResponse, StreamChunk
    ├── factory.py    ← get_llm_client() — sélection dynamique
    ├── openai.py     ← OpenAIClient
    ├── anthropic.py  ← AnthropicClient
    ├── ollama.py     ← OllamaClient
    ├── groq.py       ← GroqClient
    └── gemini.py     ← GeminiClient
```

---

## 3.2 Abstraction LLM — `services/llm/`

### Interface abstraite `LLMClient`

```
LLMClient (ABC)
├── complete(request: LLMRequest) → LLMResponse          [sync]
├── acomplete(request: LLMRequest) → LLMResponse         [async]
├── stream(request: LLMRequest) → Iterator[StreamChunk]   [sync]
├── astream(request: LLMRequest) → AsyncIterator[StreamChunk] [async]
├── get_model() → str
├── get_base_config() → dict
└── validate_capabilities(request) → None
```

Chaque implémentation hérite de `LLMClient` et reçoit un `LLMProviderConfig` dans son
constructeur. L'interface est identique quelque soit le provider — le code métier n'a
pas besoin de savoir s'il parle à OpenAI ou Ollama.

### Modèles de requête/réponse

**`LLMRequest`** — Requête unifiée vers un LLM :

```python
LLMRequest(
    messages=[...],             # list[Message] (historique)
    model="gpt-4o",             # override optionnel
    temperature=0.7,
    max_tokens=4096,
    stream=False,
    tools=[...],                # JSON Schema format OpenAI
    tool_choice="auto",
    top_p=None,
    frequency_penalty=None,
)
```

**`LLMResponse`** — Réponse normalisée :

```python
LLMResponse(
    id="resp-uuid",
    content="La réponse du LLM...",
    role=MessageRole.ASSISTANT,
    model="gpt-4o",
    finish_reason="stop",
    tool_calls=[...],           # si function calling
    usage=TokenUsage(...),
    response_time_ms=342.5,
)
```

**`StreamChunk`** — Chunk de réponse streamée :
```python
StreamChunk(delta="partie ", finish_reason=None)
StreamChunk(delta="de texte.", finish_reason="stop")
```

### Factory Pattern — `get_llm_client()`

La factory `get_llm_client(provider_config)` détermine et instancie le bon client selon
`provider_config.provider_type`. Elle gère deux cas d'erreur :

1. **`UnsupportedProviderError`** — type de provider inconnu
2. **`ImportError`** reformaté — dépendance optionnelle manquante, avec instruction
   `pip install ai-engine[provider_name]`

```python
# Providers actuellement supportés par la factory
ProviderType.OPENAI     → OpenAIClient     (nécessite: openai)
ProviderType.ANTHROPIC  → AnthropicClient  (nécessite: anthropic)
ProviderType.OLLAMA     → OllamaClient     (nécessite: ollama)
# Groq et Gemini existent mais ne sont pas encore enregistrés dans la factory
```

La fonction `list_available_providers()` teste dynamiquement quels providers sont
utilisables avec les dépendances installées.

---

## 3.3 Implémentations des clients LLM

### `OpenAIClient` — `llm/openai.py`

- Gère à la fois le client **sync** (`openai.OpenAI`) et **async** (`openai.AsyncOpenAI`)
- Support du streaming via `stream = True` dans la requête OpenAI
- Support du function calling (tools) via `tools` + `tool_choice`
- Support d'`api_base_url` pour **Azure OpenAI** et endpoints compatibles OpenAI
- Les erreurs `openai.OpenAIError` sont wrappées en `LLMError`

### `AnthropicClient` — `llm/anthropic.py`

- Clients `anthropic.Anthropic` (sync) et `anthropic.AsyncAnthropic` (async)
- La séparation du message système (champ `system` séparé dans l'API Anthropic)
  est gérée dans `_prepare_request()` — transparent pour l'appelant
- Les erreurs `anthropic.AnthropicError` → `LLMError`

### `OllamaClient` — `llm/ollama.py`

- Utilise le package `ollama` directement (pas via LangChain)
- `api_base_url` configurable (défaut : `http://localhost:11434`)
- Pas de support function calling (selon les modèles)
- La version async utilise `ollama.AsyncClient`

### `GroqClient` — `llm/groq.py`

- Interface **compatible OpenAI** (`groq.Groq` / `groq.AsyncGroq`)
- Même format de requête/réponse qu'OpenAI — migration transparente
- Conçu pour les modèles ultra-rapides (`llama-3.1-405b-reasoning`)

### `GeminiClient` — `llm/gemini.py`

- Utilise `google.generativeai` (SDK officiel Google)
- La version async appelle la version sync en attendant une API async officielle
- Conversion des messages au format `prompt` textuel pour Gemini

---

## 3.4 `AgentService` — `services/agent.py`

Service principal de gestion des agents. Reçoit un `StorageBackend` par injection
de dépendance dans son constructeur — aucune création de storage en interne.

```python
storage = SQLiteStorage("agents.db")
service = AgentService(storage)
```

### Méthodes CRUD Agents

| Méthode | Description |
|---|---|
| `create_agent(name, provider_id, ...)` | Crée et persiste un agent (vérifie que le provider existe) |
| `get_agent(agent_id)` | Récupère par ID — lève `AgentNotFoundError` si absent |
| `update_agent(agent_id, **updates)` | Mise à jour partielle (setattr + re-save) |
| `delete_agent(agent_id)` | Suppression — retourne `bool` |
| `list_agents(owner_id, role, is_active)` | Listage avec filtres optionnels |
| `get_agent_stats(agent_id)` | Statistiques : nb conversations, messages, tokens |

### Gestion des conversations

| Méthode | Description |
|---|---|
| `create_conversation(agent_id, title, metadata)` | Crée une conversation (vérifie que l'agent existe) |
| `get_conversation(conv_id)` | Récupère par ID — lève `ConversationNotFoundError` |
| `list_conversations(agent_id, owner_id)` | Listage par agent ou propriétaire |

### Chat et interactions LLM

```python
response_text, conversation = service.chat(
    agent_id="<uuid>",
    message="Quelle est la capitale de la France ?",
    conversation_id="<uuid>",   # optionnel — crée une nouvelle conv si absent
)
```

Le flux interne de `chat()` :

```
1. Vérifier que l'agent et le provider existent
2. Récupérer/créer la conversation
3. Persister le message utilisateur
4. Charger l'historique des messages
5. Construire le contexte : system_prompt + historique + nouveau message
6. Instancier le LLMClient via get_llm_client()
7. Appeler client.complete(LLMRequest(...))
8. Persister le message assistant (avec token_usage)
9. Mettre à jour les compteurs de la conversation
10. Retourner (response_text, updated_conversation)
```

En cas d'erreur LLM, le message vide est quand même persisté avec le contenu d'erreur
pour permettre le débogage.

---

## 3.5 Gestion des erreurs dans les services

Les services sont des points d'entrée métier. Ils lèvent des exceptions **typées et
informatives** :

```
AgentService.create_agent()   → ProviderNotFoundError si le provider n'existe pas
AgentService.get_agent()      → AgentNotFoundError si absent
AgentService.chat()           → AgentDisabledError si l'agent est inactif
get_llm_client()              → UnsupportedProviderError / ImportError
LLMClient.complete()          → LLMError (wrapping des erreurs provider)
LLMClient.validate_capabilities() → ValueError (streaming non supporté, etc.)
```

Voir [05-configuration-exceptions.md](05-configuration-exceptions.md) pour la hiérarchie
complète des exceptions.

---

## 3.6 Patterns de conception utilisés

### Strategy Pattern — Clients LLM

Chaque client LLM (`OpenAIClient`, `AnthropicClient`, etc.) est une stratégie
interchangeable. Le code client (AgentService) ne connaît que `LLMClient`.

```python
# Dans AgentService.chat() :
client: LLMClient = get_llm_client(provider)  # retourne la bonne stratégie
response = client.complete(request)            # interface uniforme
```

### Factory Pattern — `get_llm_client()`

Sélection dynamique de la stratégie selon le type de provider. Lazy loading des
dépendances optionnelles via import local dans la factory.

### Injection de dépendance — `AgentService(storage)`

Le storage est injecté depuis l'extérieur, facilitant les tests :

```python
# Tests : injection du storage in-memory
service = AgentService(InMemoryStorage())

# Production : injection du storage SQLite
service = AgentService(SQLiteStorage("prod.db"))
```

### Context Manager — `SQLiteStorage`

`SQLiteStorage` implémente le protocole context manager pour garantir la fermeture
de la connexion :

```python
with SQLiteStorage("agents.db") as storage:
    service = AgentService(storage)
    # connexion fermée automatiquement en sortant du bloc
```
