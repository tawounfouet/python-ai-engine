"""Tests unitaires pour ai_engine.models.knowledge."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_engine import Chunk, Document, IndexStatus, KnowledgeSource, SourceType


class TestChunk:
    def test_creation_minimal(self) -> None:
        chunk = Chunk(document_id="doc-1", content="Some text")
        assert chunk.document_id == "doc-1"
        assert chunk.content == "Some text"
        assert chunk.embedding is None
        assert chunk.chunk_index == 0
        assert chunk.metadata == {}

    def test_creation_with_embedding(self) -> None:
        chunk = Chunk(
            document_id="doc-1",
            content="Quantum computing uses qubits",
            embedding=[0.1, 0.2, 0.3, 0.4],
            chunk_index=5,
            metadata={"page": 3, "section": "Introduction"},
        )
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 4
        assert chunk.chunk_index == 5
        assert chunk.metadata["page"] == 3

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Chunk(content="no doc")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            Chunk(document_id="d")  # type: ignore[call-arg]

    def test_chunk_index_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Chunk(document_id="d", content="c", chunk_index=-1)

    def test_json_roundtrip(self) -> None:
        chunk = Chunk(
            document_id="doc-1",
            content="Test",
            embedding=[0.1, 0.2],
            chunk_index=2,
        )
        data = chunk.model_dump()
        restored = Chunk.model_validate(data)
        assert restored.id == chunk.id
        assert restored.embedding == [0.1, 0.2]


class TestDocument:
    def test_creation_minimal(self) -> None:
        doc = Document(source_id="src-1")
        assert doc.source_id == "src-1"
        assert doc.title == ""
        assert doc.content == ""
        assert doc.chunk_count == 0
        assert doc.metadata == {}

    def test_creation_full(self) -> None:
        doc = Document(
            source_id="src-1",
            title="Quantum Computing 101",
            content="Full document content here...",
            metadata={"author": "Alice", "pages": 15},
            chunk_count=30,
        )
        assert doc.title == "Quantum Computing 101"
        assert doc.chunk_count == 30
        assert doc.metadata["author"] == "Alice"

    def test_required_source_id(self) -> None:
        with pytest.raises(ValidationError):
            Document(title="No Source")  # type: ignore[call-arg]

    def test_chunk_count_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Document(source_id="s", chunk_count=-1)

    def test_json_roundtrip(self) -> None:
        doc = Document(
            source_id="src-1",
            title="Test Doc",
            content="Content",
        )
        data = doc.model_dump()
        restored = Document.model_validate(data)
        assert restored.id == doc.id
        assert restored.title == "Test Doc"


class TestKnowledgeSource:
    def test_creation_minimal(self) -> None:
        source = KnowledgeSource(
            name="Company Docs",
            source_type=SourceType.DOCUMENT,
        )
        assert source.name == "Company Docs"
        assert source.source_type == SourceType.DOCUMENT
        assert source.index_status == IndexStatus.PENDING
        assert source.chunks_count == 0
        assert source.agent_ids == []
        assert source.is_active is True
        assert source.content == ""
        assert source.file_path is None
        assert source.url is None
        assert source.last_indexed_at is None

    def test_creation_document_source(self) -> None:
        source = KnowledgeSource(
            name="PDF Report",
            source_type=SourceType.DOCUMENT,
            file_path="/data/reports/q4_2024.pdf",
            description="Q4 2024 financial report",
        )
        assert source.file_path == "/data/reports/q4_2024.pdf"

    def test_creation_url_source(self) -> None:
        source = KnowledgeSource(
            name="API Docs",
            source_type=SourceType.URL,
            url="https://docs.example.com/api",
        )
        assert source.url == "https://docs.example.com/api"

    def test_creation_text_source(self) -> None:
        source = KnowledgeSource(
            name="Inline Knowledge",
            source_type=SourceType.TEXT,
            content="Important facts about the company...",
        )
        assert source.content == "Important facts about the company..."

    def test_creation_full(self) -> None:
        now = datetime.now(UTC)
        source = KnowledgeSource(
            name="Full Source",
            description="Complete knowledge source",
            source_type=SourceType.DOCUMENT,
            file_path="/data/doc.pdf",
            index_status=IndexStatus.INDEXED,
            chunks_count=150,
            last_indexed_at=now,
            agent_ids=["agent-1", "agent-2"],
            metadata={"category": "legal"},
            is_active=True,
        )
        assert source.index_status == IndexStatus.INDEXED
        assert source.chunks_count == 150
        assert source.last_indexed_at == now
        assert len(source.agent_ids) == 2

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeSource(name="No Type")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            KnowledgeSource(source_type=SourceType.TEXT)  # type: ignore[call-arg]

    def test_chunks_count_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeSource(name="s", source_type=SourceType.TEXT, chunks_count=-1)

    def test_all_source_types(self) -> None:
        for st in SourceType:
            source = KnowledgeSource(name="Test", source_type=st)
            assert source.source_type == st

    def test_all_index_statuses(self) -> None:
        for status in IndexStatus:
            source = KnowledgeSource(name="Test", source_type=SourceType.TEXT, index_status=status)
            assert source.index_status == status

    def test_json_serialization(self) -> None:
        source = KnowledgeSource(
            name="Test",
            source_type=SourceType.URL,
            url="https://example.com",
            agent_ids=["a1", "a2"],
        )
        json_str = source.model_dump_json()
        data = json.loads(json_str)
        assert data["source_type"] == "url"
        assert data["agent_ids"] == ["a1", "a2"]

    def test_model_dump_roundtrip(self) -> None:
        source = KnowledgeSource(
            name="Roundtrip",
            source_type=SourceType.DOCUMENT,
            file_path="/data/test.pdf",
            index_status=IndexStatus.INDEXING,
            chunks_count=42,
        )
        data = source.model_dump()
        restored = KnowledgeSource.model_validate(data)
        assert restored.id == source.id
        assert restored.file_path == "/data/test.pdf"
        assert restored.index_status == IndexStatus.INDEXING
        assert restored.chunks_count == 42
