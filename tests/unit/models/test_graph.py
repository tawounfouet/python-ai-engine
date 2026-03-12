"""Tests unitaires pour ai_engine.models.graph."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_engine import Graph, GraphEdge, GraphNode, GraphStatus, NodeType


class TestGraphNode:
    def test_creation_minimal(self) -> None:
        node = GraphNode(node_id="start")
        assert node.node_id == "start"
        assert node.name == ""
        assert node.node_type == NodeType.AGENT
        assert node.config == {}
        assert node.position_x == 0.0
        assert node.position_y == 0.0

    def test_creation_full(self) -> None:
        node = GraphNode(
            node_id="researcher",
            name="Research Agent",
            node_type=NodeType.AGENT,
            description="Performs research",
            config={"agent_id": "agent-123"},
            position_x=100.0,
            position_y=200.0,
        )
        assert node.node_type == NodeType.AGENT
        assert node.config["agent_id"] == "agent-123"
        assert node.position_x == 100.0

    def test_required_node_id(self) -> None:
        with pytest.raises(ValidationError):
            GraphNode(name="No ID")  # type: ignore[call-arg]

    def test_all_node_types(self) -> None:
        for nt in NodeType:
            node = GraphNode(node_id=f"test_{nt.value}", node_type=nt)
            assert node.node_type == nt


class TestGraphEdge:
    def test_creation_minimal(self) -> None:
        edge = GraphEdge(source_node_id="a", target_node_id="b")
        assert edge.source_node_id == "a"
        assert edge.target_node_id == "b"
        assert edge.condition == ""
        assert edge.label == ""

    def test_creation_with_condition(self) -> None:
        edge = GraphEdge(
            source_node_id="check",
            target_node_id="proceed",
            condition="state['score'] > 0.8",
            label="High Score",
        )
        assert edge.condition == "state['score'] > 0.8"
        assert edge.label == "High Score"

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            GraphEdge(source_node_id="a")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            GraphEdge(target_node_id="b")  # type: ignore[call-arg]


class TestGraph:
    def test_creation_minimal(self) -> None:
        graph = Graph(name="Test", agent_id="agent-1")
        assert graph.name == "Test"
        assert graph.agent_id == "agent-1"
        assert graph.status == GraphStatus.DRAFT
        assert graph.version == 1
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.entry_node_id is None
        assert graph.state_schema == {}
        assert graph.slug == ""

    def test_creation_full(self) -> None:
        graph = Graph(
            name="Research Pipeline",
            slug="research-pipeline",
            description="Multi-step research workflow",
            agent_id="agent-1",
            owner_id="user-1",
            entry_node_id="start",
            nodes=[
                GraphNode(node_id="start", node_type=NodeType.INPUT),
                GraphNode(
                    node_id="research",
                    node_type=NodeType.AGENT,
                    config={"agent_id": "a1"},
                ),
                GraphNode(
                    node_id="review",
                    node_type=NodeType.AGENT,
                    config={"agent_id": "a2"},
                ),
                GraphNode(node_id="end", node_type=NodeType.OUTPUT),
            ],
            edges=[
                GraphEdge(source_node_id="start", target_node_id="research"),
                GraphEdge(source_node_id="research", target_node_id="review"),
                GraphEdge(source_node_id="review", target_node_id="end"),
            ],
            state_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            status=GraphStatus.ACTIVE,
            version=2,
            metadata={"created_by": "admin"},
        )
        assert len(graph.nodes) == 4
        assert len(graph.edges) == 3
        assert graph.status == GraphStatus.ACTIVE
        assert graph.version == 2
        assert graph.entry_node_id == "start"

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Graph(name="No Agent")  # type: ignore[call-arg]

    def test_version_minimum(self) -> None:
        with pytest.raises(ValidationError):
            Graph(name="Test", agent_id="a", version=0)

    def test_get_node(self) -> None:
        graph = Graph(
            name="Test",
            agent_id="a",
            nodes=[
                GraphNode(node_id="start", node_type=NodeType.INPUT),
                GraphNode(node_id="agent", node_type=NodeType.AGENT),
            ],
        )
        assert graph.get_node("start") is not None
        assert graph.get_node("start").node_type == NodeType.INPUT  # type: ignore[union-attr]
        assert graph.get_node("agent") is not None
        assert graph.get_node("nonexistent") is None

    def test_get_successors(self) -> None:
        graph = Graph(
            name="Test",
            agent_id="a",
            edges=[
                GraphEdge(source_node_id="start", target_node_id="a"),
                GraphEdge(source_node_id="start", target_node_id="b"),
                GraphEdge(source_node_id="a", target_node_id="end"),
            ],
        )
        successors = graph.get_successors("start")
        assert len(successors) == 2
        target_ids = {e.target_node_id for e in successors}
        assert target_ids == {"a", "b"}

    def test_get_predecessors(self) -> None:
        graph = Graph(
            name="Test",
            agent_id="a",
            edges=[
                GraphEdge(source_node_id="a", target_node_id="end"),
                GraphEdge(source_node_id="b", target_node_id="end"),
            ],
        )
        predecessors = graph.get_predecessors("end")
        assert len(predecessors) == 2
        source_ids = {e.source_node_id for e in predecessors}
        assert source_ids == {"a", "b"}

    def test_get_successors_empty(self) -> None:
        graph = Graph(name="Test", agent_id="a")
        assert graph.get_successors("any") == []

    def test_all_statuses(self) -> None:
        for status in GraphStatus:
            graph = Graph(name="Test", agent_id="a", status=status)
            assert graph.status == status

    def test_json_serialization(self) -> None:
        graph = Graph(
            name="Test",
            agent_id="a",
            nodes=[GraphNode(node_id="start", node_type=NodeType.INPUT)],
            edges=[GraphEdge(source_node_id="start", target_node_id="end")],
        )
        json_str = graph.model_dump_json()
        data = json.loads(json_str)
        assert data["name"] == "Test"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["node_type"] == "input"

    def test_model_dump_roundtrip(self) -> None:
        graph = Graph(
            name="Roundtrip",
            agent_id="a",
            entry_node_id="start",
            nodes=[
                GraphNode(node_id="start", node_type=NodeType.INPUT),
                GraphNode(node_id="end", node_type=NodeType.OUTPUT),
            ],
            edges=[GraphEdge(source_node_id="start", target_node_id="end")],
            version=3,
        )
        data = graph.model_dump()
        restored = Graph.model_validate(data)
        assert restored.id == graph.id
        assert restored.version == 3
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1
