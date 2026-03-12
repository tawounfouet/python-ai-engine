"""
AI Engine Models — Knowledge (Knowledge Sources for RAG).

Conversion du modèle Django `KnowledgeSource` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/knowledge.py

Ajouts standalone :
  - `Document` : document parsé à partir d'une source
  - `Chunk` : fragment de document indexé avec embedding

Le Django `FileField` est remplacé par `file_path: str | None`.
Le Django `ManyToManyField` agents est remplacé par `agent_ids: list[str]`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import IndexStatus, SourceType


class Chunk(BaseModel):
    """
    Fragment de document indexé pour le RAG.

    Chaque chunk est un morceau de texte avec son embedding,
    prêt pour la recherche sémantique.

    Usage:
        chunk = Chunk(
            document_id="doc-uuid",
            content="Quantum computing uses qubits...",
            embedding=[0.1, 0.2, ...],
            chunk_index=0,
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Document parent (référence par ID)
    document_id: str = Field(
        ...,
        description="ID du Document parent",
    )

    # Contenu
    content: str = Field(
        ...,
        description="Texte du fragment",
    )

    # Embedding
    embedding: list[float] | None = Field(
        default=None,
        description="Vecteur d'embedding pour recherche sémantique",
    )

    # Position dans le document
    chunk_index: int = Field(
        default=0,
        ge=0,
        description="Index du chunk dans le document (0-based)",
    )

    # Metadata (page number, section, etc.)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Document(BaseModel):
    """
    Document parsé à partir d'une KnowledgeSource.

    Représente un document complet avant découpage en chunks.

    Usage:
        doc = Document(
            source_id="source-uuid",
            title="Quantum Computing 101",
            content="Full document content...",
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Source parente (référence par ID)
    source_id: str = Field(
        ...,
        description="ID de la KnowledgeSource parente",
    )

    # Contenu
    title: str = Field(
        default="",
        description="Titre du document",
    )
    content: str = Field(
        default="",
        description="Contenu complet du document",
    )

    # Metadata (author, page_count, file_type, etc.)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Compteurs
    chunk_count: int = Field(
        default=0,
        ge=0,
        description="Nombre de chunks générés",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KnowledgeSource(BaseModel):
    """
    Source de connaissance pour le RAG.

    Équivalent standalone du modèle Django `KnowledgeSource`.

    Usage:
        source = KnowledgeSource(
            name="Company Docs",
            source_type=SourceType.DOCUMENT,
            file_path="/data/company_docs.pdf",
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""

    # Type de source
    source_type: SourceType

    # Source — selon le type :
    content: str = Field(
        default="",
        description="Contenu brut (si source_type=text)",
    )
    file_path: str | None = Field(
        default=None,
        description="Chemin vers le fichier (si source_type=document). Remplace Django FileField.",
    )
    url: str | None = Field(
        default=None,
        description="URL de la source (si source_type=url)",
    )

    # Indexation
    index_status: IndexStatus = IndexStatus.PENDING
    chunks_count: int = Field(
        default=0,
        ge=0,
        description="Nombre de chunks après découpage",
    )
    last_indexed_at: datetime | None = None

    # Agents ayant accès (références par ID — remplace ManyToManyField)
    agent_ids: list[str] = Field(
        default_factory=list,
        description="IDs des Agents ayant accès à cette source",
    )

    # Métadonnées
    metadata: dict[str, Any] = Field(default_factory=dict)

    # État
    is_active: bool = True

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
