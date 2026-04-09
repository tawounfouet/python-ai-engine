# 📋 Changelog Index

All notable changes to **AI Engine** are documented here, one file per release.  
Versioning follows [Semantic Versioning](https://semver.org/).

---

## Releases

| Version | File | Highlights |
|---------|------|------------|
| [0.5.3](#053---django-adapter) | [`0.5.3_django_adapter.md`](0.5.3_django_adapter.md) | Django adapter — DRF views, `DjangoORMStorage`, 36 tests |
| [0.5.2](#052---fastapi-adapter) | [`0.5.2_fastapi_adapter.md`](0.5.2_fastapi_adapter.md) | FastAPI adapter — REST + SSE streaming, 34 tests |
| [0.5.1](#051---cli-adapter) | [`0.5.1_cli_adapter.md`](0.5.1_cli_adapter.md) | CLI adapter — Typer + Rich, 19 command tests |
| [0.5.0](#050---phase-5-start) | [`0.5.0_phase5.md`](0.5.0_phase5.md) | Phase 5 kick-off — adapter scaffolding |
| [0.4.0](#040---phase-4-tools-skills-eventbus) | [`0.4.0_phase4_completed.md`](0.4.0_phase4_completed.md) | Tool system, Skills, EventBus — Phase 4 complete |
| [0.3.0](#030---services-layer) | [`0.3.0_phase3.md`](0.3.0_phase3.md) | AgentService, ConversationService, LLM Factory |
| [0.2.0](#020---storage-layer) | [`0.2.0_phase2.md`](0.2.0_phase2.md) | StorageBackend ABC, InMemoryStorage, SQLiteStorage |
| [0.1.0](#010---phase-1-domain-models) | [`0.1.0_phase1.md`](0.1.0_phase1.md) | Pydantic domain models, project structure |

---

## 0.5.3 — Django Adapter

**Date**: April 2026 · **File**: [`0.5.3_django_adapter.md`](0.5.3_django_adapter.md)

Full Django integration via [Django REST Framework](https://www.django-rest-framework.org/).

### What's new
- **`DjangoORMStorage`** — `StorageBackend` implementation backed by the Django ORM.  
  Strategy: *index columns + `JSONField`* stores filterable columns alongside a full Pydantic JSON blob.
- **4 ORM models** (`app_label = "ai_engine"`):  
  `ProviderRecord` · `AgentRecord` · `ConversationRecord` · `MessageRecord`
- **DRF views** — `ProviderListCreateView`, `ProviderDetailView`, `AgentListCreateView`,  
  `AgentDetailView`, `ConversationListCreateView`, `ConversationDetailView`,  
  `ConversationMessageListView`, `ChatView`
- **Serializers** — Provider / Agent / Conversation / Message + Create / Update variants
- **URL patterns** — ready to `include()` under any prefix
- **`AiEngineConfig`** — `AppConfig` that wires the Django signals bridge on startup
- **Django signals relay** — forwards AI Engine domain events into the `EventBus`
- **Admin** — all 4 models registered in `django.contrib.admin`
- **36 new tests** — ORM models, storage CRUD, serializers, all views; `conftest.py` uses  
  `schema_editor.create_model()` so no `migrations/` directory is needed in tests

### Quick example

```python
# settings.py
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "ai_engine.adapters.django",
]
AI_ENGINE = {"EVENT_BUS_ENABLED": True}

# urls.py
from django.urls import path, include
from ai_engine.adapters.django.urls import urlpatterns as ai_engine_urls

urlpatterns = [
    path("api/ai/", include((ai_engine_urls, "ai_engine"))),
]
```

```bash
python manage.py migrate   # creates the 4 ai_engine_* tables
```

```python
# Anywhere in your Django project
from ai_engine.adapters.django import DjangoORMStorage
from ai_engine.services import AgentService
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.types import ProviderType

storage = DjangoORMStorage()
svc = AgentService(storage)

provider = storage.save_provider(LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key="sk-...",
    is_default=True,
))

agent = svc.create_agent(
    name="Support Bot",
    provider_id=provider.id,
    system_prompt="You are a helpful customer support agent.",
)

response, conversation = svc.chat(
    agent_id=agent.id,
    message="How do I reset my password?",
)
print(response.content)
```

### Test coverage delta

| Scope | Tests |
|-------|-------|
| Before (Phase 5.2 baseline) | 655 passing, 1 xfail |
| Added by Phase 5.3 | +36 Django |
| **Total** | **691 passing, 1 xfail** |

---

## 0.5.2 — FastAPI Adapter

**Date**: April 2026 · **File**: [`0.5.2_fastapi_adapter.md`](0.5.2_fastapi_adapter.md)

REST API adapter with automatic OpenAPI docs and SSE streaming.

### What's new
- **`create_router(db, ...)`** — mountable `APIRouter` exposing all ai_engine resources
- **Schemas** — Pydantic request/response models (Provider, Agent, Conversation, Message, Chat, Pagination)
- **Dependencies** — `get_storage`, `get_agent_service`, `Pagination` FastAPI deps
- **Exception handlers** — `register_handlers(app)` maps domain exceptions → HTTP 404/500
- **Routers** — `providers`, `agents`, `conversations`, `chat` (sync + SSE stream)
- **Bug fix** — `AgentService.create_agent()`: `kwargs.pop("slug")` instead of `kwargs.get("slug")` to avoid duplicate kwarg error
- 34 new tests

### Quick example

```python
from fastapi import FastAPI
from ai_engine.adapters.fastapi import create_router
from ai_engine.adapters.fastapi.exception_handlers import register_handlers

app = FastAPI(title="My AI App")
register_handlers(app)
app.include_router(create_router("app.db"), prefix="/api")
```

---

## 0.5.1 — CLI Adapter

**Date**: April 2026 · **File**: [`0.5.1_cli_adapter.md`](0.5.1_cli_adapter.md)

Interactive terminal interface powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).

### What's new
- Commands: `provider` · `agent` · `conversation` · `chat` · `config`
- Interactive chat REPL + single-shot `--once` mode (pipeable)
- Rich tables and formatted output throughout
- 19 command tests + 16 utility tests

### Quick example

```bash
ai-engine provider add --name "OpenAI" --type openai --model gpt-4o --key sk-...
ai-engine agent create --name "Assistant" --provider "OpenAI" --prompt "You are helpful."
ai-engine chat --agent assistant
```

---

## 0.5.0 — Phase 5 Start

**Date**: April 2026 · **File**: [`0.5.0_phase5.md`](0.5.0_phase5.md)

Phase 5 kick-off: adapter scaffolding, `pyproject.toml` optional dependency groups (`cli`, `fastapi`, `django`), and the adapter package skeleton.

---

## 0.4.0 — Phase 4: Tools, Skills & EventBus

**File**: [`0.4.0_phase4_completed.md`](0.4.0_phase4_completed.md)

- **Tool System**: `BaseTool` ABC + `CalculatorTool`, `DuckDuckGoSearchTool`, `SerperSearchTool`, `HttpGetTool`, `HttpPostTool`
- **Skills System**: `BaseSkill` ABC + `SkillRegistry` with tool-requirement validation
- **EventBus**: in-process pub/sub with sync/async handlers, wildcard listeners, middleware, error isolation
- 20 typed event classes covering the full agent lifecycle

---

## 0.3.0 — Services Layer

**File**: [`0.3.0_phase3.md`](0.3.0_phase3.md)

- `AgentService` — full agent lifecycle orchestration
- `ConversationService` — context compilation and message history
- `LLMFactory` — dynamic registry for OpenAI, Anthropic, Ollama, Gemini, Groq

---

## 0.2.0 — Storage Layer

**File**: [`0.2.0_phase2.md`](0.2.0_phase2.md)

- `StorageBackend` ABC — pluggable persistence interface
- `InMemoryStorage` — fast in-process backend (testing / prototyping)
- `SQLiteStorage` — file-based persistence (production single-process use)

---

## 0.1.0 — Phase 1: Domain Models

**File**: [`0.1.0_phase1.md`](0.1.0_phase1.md)

- Pydantic domain models: `Agent`, `LLMProviderConfig`, `Conversation`, `Message`, `Tool`, `Skill`, `Memory`, `KnowledgeSource`, `ExecutionGraph`
- `types.py` — all `StrEnum` types (`ProviderType`, `AgentRole`, `EventType`, …)
- `exceptions.py` — full exception hierarchy
- `config.py` — pydantic-settings configuration
