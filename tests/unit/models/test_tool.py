"""Tests unitaires pour ai_engine.models.tool."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_engine import ToolDefinition, ToolType


class TestToolDefinition:
    def test_creation_minimal(self) -> None:
        tool = ToolDefinition(key="test_tool", name="Test Tool")
        assert tool.key == "test_tool"
        assert tool.name == "Test Tool"
        assert tool.tool_type == ToolType.FUNCTION
        assert tool.id  # uuid auto
        assert tool.is_active is True
        assert tool.requires_approval is False
        assert tool.is_dangerous is False
        assert tool.parameters_schema == {}
        assert tool.config == {}

    def test_creation_full(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }
        tool = ToolDefinition(
            key="web_search",
            name="Web Search",
            description="Search the web",
            tool_type=ToolType.API,
            parameters_schema=schema,
            function_path="ai_engine.tools.web_search.execute",
            connector_id="conn-123",
            config={"timeout": 30, "max_results": 10},
            requires_approval=True,
            is_dangerous=False,
            metadata={"version": "2.0"},
        )
        assert tool.tool_type == ToolType.API
        assert tool.parameters_schema["required"] == ["query"]
        assert tool.function_path == "ai_engine.tools.web_search.execute"
        assert tool.connector_id == "conn-123"
        assert tool.requires_approval is True

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ToolDefinition(name="No Key")  # type: ignore[call-arg]

    def test_get_function_schema(self) -> None:
        tool = ToolDefinition(
            key="calc",
            name="Calculator",
            description="Do math",
            parameters_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
        )
        schema = tool.get_function_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calc"
        assert schema["function"]["description"] == "Do math"
        assert "properties" in schema["function"]["parameters"]

    def test_get_function_schema_empty(self) -> None:
        tool = ToolDefinition(key="noop", name="Noop")
        schema = tool.get_function_schema()
        assert schema["function"]["name"] == "noop"
        assert schema["function"]["parameters"] == {}

    def test_dangerous_tool(self) -> None:
        tool = ToolDefinition(
            key="delete_all",
            name="Delete All",
            description="Deletes everything",
            is_dangerous=True,
            requires_approval=True,
        )
        assert tool.is_dangerous is True
        assert tool.requires_approval is True

    def test_all_tool_types(self) -> None:
        for tt in ToolType:
            tool = ToolDefinition(key=f"test_{tt.value}", name=f"Test {tt.value}", tool_type=tt)
            assert tool.tool_type == tt

    def test_json_roundtrip(self) -> None:
        tool = ToolDefinition(
            key="search",
            name="Search",
            tool_type=ToolType.API,
            parameters_schema={"type": "object", "properties": {}},
        )
        data = tool.model_dump()
        restored = ToolDefinition.model_validate(data)
        assert restored.key == tool.key
        assert restored.id == tool.id

    def test_json_serialization(self) -> None:
        tool = ToolDefinition(key="test", name="Test", tool_type=ToolType.CONNECTOR)
        json_str = tool.model_dump_json()
        data = json.loads(json_str)
        assert data["tool_type"] == "connector"
        assert data["key"] == "test"

    def test_unique_ids(self) -> None:
        t1 = ToolDefinition(key="a", name="A")
        t2 = ToolDefinition(key="b", name="B")
        assert t1.id != t2.id
