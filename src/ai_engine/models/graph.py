"""
AI Engine Models — Graph (Workflow LangGraph-style).

Conversion du modèle Django `Graph` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/graph.py

Le JSONField `definition` opaque de Django est éclaté en types forts :
  - `nodes: list[GraphNode]` — nœuds du graphe
  - `edges: list[GraphEdge]` — arêtes du graphe
  - `entry_node_id: str | None` — point d'entrée
  - `state_schema: dict` — schéma d'état du graphe
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import GraphStatus, NodeType


class GraphNode(BaseModel):
    """
    Nœud dans un graph de workflow AI.

    Chaque nœud représente une étape : appel d'agent, condition,
    outil, entrée, sortie, parallélisme ou boucle.

    Usage:
        node = GraphNode(
            node_id="researcher",
            name="Research Agent",
            node_type=NodeType.AGENT,
            config={"agent_id": "agent-uuid"},
        )
    """

    node_id: str = Field(
        ...,
        description="Identifiant unique du nœud dans le graphe",
    )
    name: str = Field(
        default="",
        description="Nom lisible du nœud",
    )
    node_type: NodeType = NodeType.AGENT
    description: str = ""

    # Configuration spécifique au type de nœud
    # - AGENT: {"agent_id": "...", "system_prompt_override": "..."}
    # - CONDITION: {"condition_expr": "state['score'] > 0.8"}
    # - TOOL: {"tool_id": "...", "tool_key": "web_search"}
    # - PARALLEL: {"branch_node_ids": ["a", "b"]}
    # - LOOP: {"max_iterations": 5, "break_condition": "..."}
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration spécifique au type de nœud",
    )

    # Position visuelle (pour les éditeurs de graph)
    position_x: float = 0.0
    position_y: float = 0.0


class GraphEdge(BaseModel):
    """
    Arête (connexion) entre deux nœuds d'un graph.

    Usage:
        edge = GraphEdge(
            source_node_id="researcher",
            target_node_id="writer",
            condition="state['research_done'] == True",
        )
    """

    source_node_id: str = Field(
        ...,
        description="ID du nœud source",
    )
    target_node_id: str = Field(
        ...,
        description="ID du nœud cible",
    )
    condition: str = Field(
        default="",
        description="Condition pour emprunter cette arête (vide = toujours)",
    )
    label: str = Field(
        default="",
        description="Label lisible de l'arête",
    )


class Graph(BaseModel):
    """
    Graphe de workflow AI (LangGraph-style).

    Décrit un workflow multi-nœuds pour un agent,
    où chaque nœud est une étape de raisonnement/action.

    Équivalent standalone du modèle Django `Graph`.
    Le JSONField `definition` est éclaté en `nodes`, `edges`,
    `entry_node_id` et `state_schema`.

    Usage:
        graph = Graph(
            name="Research Pipeline",
            slug="research-pipeline",
            agent_id="agent-uuid",
            entry_node_id="start",
            nodes=[
                GraphNode(node_id="start", node_type=NodeType.INPUT),
                GraphNode(node_id="researcher", node_type=NodeType.AGENT),
                GraphNode(node_id="end", node_type=NodeType.OUTPUT),
            ],
            edges=[
                GraphEdge(source_node_id="start", target_node_id="researcher"),
                GraphEdge(source_node_id="researcher", target_node_id="end"),
            ],
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    slug: str = ""
    description: str = ""

    # Agent propriétaire (référence par ID — remplace ForeignKey)
    agent_id: str = Field(
        ...,
        description="ID de l'Agent qui exécute ce graph",
    )

    # Ownership (framework-agnostic)
    owner_id: str | None = Field(
        default=None,
        description="ID du propriétaire (user_id, tenant_id, etc.)",
    )

    # Définition du graph — éclatée depuis le JSONField `definition` de Django
    nodes: list[GraphNode] = Field(
        default_factory=list,
        description="Nœuds du graphe",
    )
    edges: list[GraphEdge] = Field(
        default_factory=list,
        description="Arêtes (connexions) entre les nœuds",
    )
    entry_node_id: str | None = Field(
        default=None,
        description="ID du nœud d'entrée du graphe",
    )
    state_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="Schéma JSON de l'état partagé du graphe",
    )

    # Status
    status: GraphStatus = GraphStatus.DRAFT

    # Version
    version: int = Field(default=1, ge=1)

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get_node(self, node_id: str) -> GraphNode | None:
        """Retourne un nœud par son ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_successors(self, node_id: str) -> list[GraphEdge]:
        """Retourne les arêtes sortantes d'un nœud."""
        return [edge for edge in self.edges if edge.source_node_id == node_id]

    def get_predecessors(self, node_id: str) -> list[GraphEdge]:
        """Retourne les arêtes entrantes d'un nœud."""
        return [edge for edge in self.edges if edge.target_node_id == node_id]
