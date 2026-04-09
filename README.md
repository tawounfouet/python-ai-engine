# 🚀 AI Engine

A standalone, framework-agnostic Python package providing a robust foundation for building sophisticated AI agent applications. Originally extracted from a Django monolith (`django-ai-app`), this engine provides reusable, scalable, and fully-typed AI logic across any context — scripts, notebooks, FastAPI, Django, Lambda, CLI, and more.

---

## ✨ Features

- 🧱 **Data Models (Pydantic)**: Strictly-typed domain models for Agents, Providers, Tools, Skills, Memories, and Multi-Agent Graphs.
- 💾 **Abstract Storage Layer**: Pluggable persistence module allowing AI logic to work decoupled from any specific ORM or database. Ships with `InMemoryStorage` and `SQLiteStorage` out of the box.
- 🧠 **LLM Factory**: Universal registry/factory interface for dynamically creating LLM clients. Supports **OpenAI**, **Anthropic**, **Ollama**, **Gemini**, and **Groq** out of the box.
- 🤖 **Agent Service**: Complete orchestration of the Agent lifecycle, context compilation, and conversation histories.
- 🛠 **Tool System**: `BaseTool` ABC for defining custom tools + four ready-to-use concrete tools: `CalculatorTool`, `DuckDuckGoSearchTool`, `SerperSearchTool`, `HttpGetTool`, `HttpPostTool`.
- 🧩 **Skills System**: `BaseSkill` ABC for high-level agent capabilities + `SkillRegistry` for dynamic registration, discovery, and tool-requirement validation.
- 📡 **EventBus**: Lightweight in-process event bus with sync/async handler support, wildcard listeners, middleware, and error isolation. Fully decouples internal components without Django Signals.
- 🔌 **Framework Adapters**: Effortlessly embed the AI Engine into an existing Django or FastAPI app using drop-in adapters *(Upcoming — Phase 5)*.

---

## 📦 Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone <repository_url>
cd ai_engine

# Install all dependencies
uv sync
```

> Once published, the package will be installable via `pip install ai_engine`.

---

## 🚀 Quick Start

### Agent Service (Phases 1–3)

```python
from ai_engine.services import AgentService
from ai_engine.storage.sqlite import SQLiteStorage
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.types import ProviderType

# 1. Initialize storage & service
storage = SQLiteStorage("app.db")
agent_service = AgentService(storage)

# 2. Configure a provider
provider = storage.save_provider(LLMProviderConfig(
    name="OpenAI GPT-4o",
    provider_type=ProviderType.OPENAI,
    default_model="gpt-4o",
    api_key="sk-...",
))

# 3. Create an agent
agent = agent_service.create_agent(
    name="Code Reviewer",
    provider_id=provider.id,
    system_prompt="You are an expert, uncompromising code reviewer.",
)

# 4. Chat — context and history are maintained automatically
response, conversation = agent_service.chat(
    agent_id=agent.id,
    message="What do you think of writing the entire app in a single file?",
)
print(f"Agent ({response.model}): {response.content}")
```

---

### Tool System (Phase 4)

```python
from ai_engine import BaseTool, CalculatorTool, DuckDuckGoSearchTool

# Use a built-in tool
calc = CalculatorTool()
print(calc(expression="2 ** 10 + sqrt(144)"))  # "1036.0"

# Define a custom tool
class WeatherTool(BaseTool):
    key = "get_weather"
    name = "Get Weather"
    description = "Returns the current weather for a given city."
    parameters_schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }

    def run(self, city: str) -> str:
        return f"Sunny, 22 °C in {city}"  # Replace with a real API call

weather = WeatherTool()
print(weather(city="Paris"))              # Sync call via __call__
print(await weather.arun(city="Tokyo"))   # Async call (auto-threaded if not overridden)

# Export schema for LLM function-calling (OpenAI / Anthropic format)
print(weather.get_function_schema())
```

---

### Skills System (Phase 4)

```python
from ai_engine import BaseSkill, SkillRegistry, DuckDuckGoSearchTool
from ai_engine.types import SkillCategory

class ResearchSkill(BaseSkill):
    key = "research"
    name = "Research Assistant"
    description = "Searches the web and summarizes results."
    category = SkillCategory.RESEARCH
    required_tool_keys = ["duckduckgo_search"]

    def run(self, query: str, *, llm_client, **kwargs) -> str:
        search = DuckDuckGoSearchTool()
        results = search(query=query)
        # … pass results to llm_client.complete() for summarization …
        return f"Summary for: {query}"

# Register and use
registry = SkillRegistry()
registry.register(ResearchSkill())

skill = registry.get("research")
output = skill.execute(query="latest AI research", llm_client=my_llm)
```

---

### EventBus (Phase 4)

```python
from ai_engine import ToolSucceededEvent, get_event_bus
from ai_engine.types import EventType

bus = get_event_bus()  # Global singleton, shared across the application

# Sync handler
@bus.on(EventType.TOOL_SUCCEEDED)
def on_tool_done(event: ToolSucceededEvent) -> None:
    print(f"✅ Tool '{event.tool_name}' finished in {event.duration_ms:.1f} ms")

# Async handler
@bus.on(EventType.TOOL_FAILED)
async def on_tool_error(event) -> None:
    await alert_team(event.error)

# Wildcard — fires for every event regardless of type
@bus.on("*")
def audit_log(event) -> None:
    print(f"[AUDIT] {event.event_type} @ {event.timestamp}")

# Emit events (sync or async)
bus.emit(ToolSucceededEvent(tool_name="calculator", tool_call_id="tc-1", duration_ms=3.2))
await bus.aemit(ToolSucceededEvent(tool_name="search", tool_call_id="tc-2", duration_ms=210.0))
```

---

## 🗺️ Migration Roadmap (Status)

The extraction of this engine from the original Django monolith is structured into 6 phases:

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Structure & Pydantic Domain Models | ✅ Complete |
| **Phase 2** | Storage Layer (Interfaces & Backends) | ✅ Complete |
| **Phase 3** | Services Layer (LLM Factory & Agent Service) | ✅ Complete |
| **Phase 4** | Tool System, Skills & EventBus | ✅ Complete |
| **Phase 5** | Framework Adapters (Django, FastAPI, CLI) | ⏳ Upcoming |
| **Phase 6** | Robust Test Coverage & PyPI Publishing | ⏳ Upcoming |

For full architecture details, see [`docs/implementation.md`](docs/implementation.md) and [`docs/etat_avancement.md`](docs/etat_avancement.md).

---

## 🧪 Testing

The engine is built with a test-first approach. All phases have dedicated unit and integration test suites.

```bash
# Run the full test suite
uv run pytest tests/ -v

# Run only Phase 4 tests (tools, events, skills)
uv run pytest tests/unit/tools/ tests/unit/events/ tests/unit/skills/ -v

# Run the Phase 4 demo script
uv run python examples/09_phase4_tools_skills_events.py
```

**Current coverage**: 546 tests passing, 0 failures (+ 1 expected xfail).

---

## 📂 Project Structure

```
ai_engine/
├── src/ai_engine/
│   ├── models/          # Pydantic domain models (Agent, Tool, Skill, …)
│   ├── storage/         # StorageBackend ABC + InMemoryStorage + SQLiteStorage
│   ├── services/        # AgentService, ConversationService, LLM Factory
│   ├── tools/           # BaseTool ABC + CalculatorTool, SearchTools, HttpTools
│   ├── skills/          # BaseSkill ABC + SkillRegistry
│   ├── events/          # EventBus + 20 typed event classes
│   ├── types.py         # All StrEnum types (ProviderType, EventType, …)
│   ├── exceptions.py    # Full exception hierarchy
│   └── config.py        # Settings (pydantic-settings)
├── tests/
│   └── unit/            # Unit tests per module
├── examples/            # Runnable usage examples (01–09)
└── docs/                # Architecture docs, progress tracker, changelogs
```

---

## ⚖️ License

Standard Open-Source / Internal project license.