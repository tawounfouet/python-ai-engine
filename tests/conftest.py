"""
AI Engine — Test fixtures communes.

Fournit des instances pré-configurées de tous les models
pour les tests unitaires et d'intégration.
"""

from __future__ import annotations

import pytest

from ai_engine import (
    Agent,
    AgentConfig,
    AgentRole,
    Conversation,
    Execution,
    Graph,
    GraphEdge,
    GraphNode,
    GraphStatus,
    LLMProviderConfig,
    Message,
    MessageRole,
    NodeType,
    ProviderType,
    Skill,
    SkillCategory,
    TokenUsage,
    ToolDefinition,
    ToolType,
)

# ── Provider Fixtures ──


@pytest.fixture
def provider() -> LLMProviderConfig:
    return LLMProviderConfig(
        name="Test OpenAI",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key="sk-test-key-123",
    )


@pytest.fixture
def provider_anthropic() -> LLMProviderConfig:
    return LLMProviderConfig(
        name="Test Anthropic",
        provider_type=ProviderType.ANTHROPIC,
        default_model="claude-3-opus-20240229",
        api_key="sk-ant-test-key",
    )


# ── Agent Fixtures ──


@pytest.fixture
def agent(provider: LLMProviderConfig) -> Agent:
    return Agent(
        name="Test Assistant",
        slug="test-assistant",
        role=AgentRole.ASSISTANT,
        provider_id=provider.id,
        system_prompt="You are a helpful test assistant.",
    )


@pytest.fixture
def agent_researcher(provider: LLMProviderConfig) -> Agent:
    return Agent(
        name="Test Researcher",
        slug="test-researcher",
        role=AgentRole.RESEARCHER,
        provider_id=provider.id,
        system_prompt="You are a research agent.",
        config=AgentConfig(max_iterations=20, enable_rag=True),
    )


# ── Tool Fixtures ──


@pytest.fixture
def tool_web_search() -> ToolDefinition:
    return ToolDefinition(
        key="web_search",
        name="Web Search",
        description="Search the web for information",
        tool_type=ToolType.API,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    )


@pytest.fixture
def tool_calculator() -> ToolDefinition:
    return ToolDefinition(
        key="calculator",
        name="Calculator",
        description="Perform mathematical calculations",
        tool_type=ToolType.FUNCTION,
        function_path="ai_engine.tools.calculator.execute",
    )


# ── Skill Fixtures ──


@pytest.fixture
def skill_research() -> Skill:
    return Skill(
        key="research",
        name="Research Skill",
        description="Combine web search and summarization",
        category=SkillCategory.RESEARCH,
        system_prompt="You are an expert researcher.",
    )


# ── Conversation Fixtures ──


@pytest.fixture
def conversation(agent: Agent) -> Conversation:
    return Conversation(
        title="Test Conversation",
        agent_id=agent.id,
        owner_id="user-123",
    )


# ── Message Fixtures ──


@pytest.fixture
def message_user(conversation: Conversation) -> Message:
    return Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="What is quantum computing?",
    )


@pytest.fixture
def message_assistant(conversation: Conversation) -> Message:
    return Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Quantum computing uses qubits...",
        token_usage=TokenUsage(
            prompt_tokens=10,
            completion_tokens=50,
            total_tokens=60,
            estimated_cost_usd=0.001,
        ),
    )


# ── Graph Fixtures ──


@pytest.fixture
def graph(agent: Agent) -> Graph:
    return Graph(
        name="Test Pipeline",
        slug="test-pipeline",
        agent_id=agent.id,
        entry_node_id="start",
        nodes=[
            GraphNode(node_id="start", name="Start", node_type=NodeType.INPUT),
            GraphNode(node_id="researcher", name="Researcher", node_type=NodeType.AGENT),
            GraphNode(node_id="end", name="End", node_type=NodeType.OUTPUT),
        ],
        edges=[
            GraphEdge(source_node_id="start", target_node_id="researcher"),
            GraphEdge(source_node_id="researcher", target_node_id="end"),
        ],
        status=GraphStatus.ACTIVE,
    )


# ── Execution Fixtures ──


@pytest.fixture
def execution(agent: Agent) -> Execution:
    return Execution(
        agent_id=agent.id,
        input_data={"prompt": "Test prompt"},
    )
