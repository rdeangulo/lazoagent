"""
Lazo Agent — Knowledge Base Service

Manages the RAG pipeline:
1. Document upload and chunking
2. Embedding generation via OpenAI
3. Vector storage in pgvector
4. Similarity search for AI tool queries
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from app.config import settings
from app.core.exceptions import EmbeddingError, KnowledgeError

logger = logging.getLogger(__name__)

# Chunking parameters
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200


class KnowledgeService:
    """Manages the knowledge base: documents, chunking, embeddings, search."""

    # ── Document Management ──────────────────────────────────────────────

    async def upload_document(
        self,
        title: str,
        content: str,
        doc_type: str = "general",
        description: Optional[str] = None,
        uploaded_by_id: Optional[UUID] = None,
    ) -> dict:
        """Upload a new document, chunk it, and generate embeddings."""
        from app.core.database import get_db_context
        from app.models import KnowledgeDocument

        async with get_db_context() as db:
            doc = KnowledgeDocument(
                title=title,
                content=content,
                doc_type=doc_type,
                description=description,
                status="processing",
                uploaded_by_id=uploaded_by_id,
            )
            db.add(doc)
            await db.flush()
            doc_id = doc.id

        # Process in background (chunk + embed)
        import asyncio
        asyncio.create_task(self._process_document(doc_id))

        return {"document_id": str(doc_id), "status": "processing"}

    async def _process_document(self, document_id: UUID):
        """Chunk the document and generate embeddings."""
        from app.core.database import get_db_context
        from app.models import KnowledgeChunk, KnowledgeDocument
        from sqlalchemy import select

        try:
            async with get_db_context() as db:
                stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
                result = await db.execute(stmt)
                doc = result.scalar_one_or_none()

                if not doc or not doc.content:
                    return

                # Chunk the content
                chunks = self._chunk_text(doc.content)

                # Generate embeddings
                embeddings = await self._generate_embeddings([c for c in chunks])

                # Store chunks with embeddings
                for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk = KnowledgeChunk(
                        document_id=document_id,
                        content=chunk_text,
                        chunk_index=i,
                        embedding=embedding,
                    )
                    db.add(chunk)

                doc.status = "ready"
                doc.chunk_count = len(chunks)

                logger.info(
                    "Processed document '%s': %d chunks", doc.title, len(chunks)
                )

        except Exception as e:
            logger.exception("Failed to process document %s", document_id)
            try:
                async with get_db_context() as db:
                    stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
                    result = await db.execute(stmt)
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = "error"
                        doc.error_message = str(e)
            except Exception:
                pass

    # ── Search ───────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Search the knowledge base using vector similarity.

        Returns the most relevant chunks with their source documents.
        """
        from app.core.database import get_db_context
        from app.models import KnowledgeChunk, KnowledgeDocument
        from sqlalchemy import select, text

        # Generate query embedding
        query_embedding = await self._generate_embeddings([query])
        if not query_embedding:
            return []

        embedding_vector = query_embedding[0]

        async with get_db_context() as db:
            # pgvector cosine similarity search using SQLAlchemy column expressions
            from pgvector.sqlalchemy import Vector
            from sqlalchemy import cast, literal_column, func

            embedding_str = "[" + ",".join(str(x) for x in embedding_vector) + "]"

            # Build query using SQLAlchemy ORM with pgvector distance operator
            distance = KnowledgeChunk.embedding.cosine_distance(embedding_vector)
            score_expr = (1 - distance).label("score")

            stmt = (
                select(
                    KnowledgeChunk.id,
                    KnowledgeChunk.content,
                    KnowledgeChunk.chunk_index,
                    KnowledgeDocument.title.label("document_title"),
                    KnowledgeDocument.doc_type,
                    score_expr,
                )
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(KnowledgeDocument.status == "ready")
                .where(KnowledgeChunk.embedding.is_not(None))
                .order_by(distance)
                .limit(limit)
            )

            if doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

            result = await db.execute(stmt)

            rows = result.all()
            return [
                {
                    "chunk_id": str(row.id),
                    "content": row.content,
                    "document_title": row.document_title,
                    "doc_type": row.doc_type.value if hasattr(row.doc_type, 'value') else str(row.doc_type),
                    "score": float(row.score),
                }
                for row in rows
            ]

    # ── Helpers ──────────────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE

            # Try to break at a sentence boundary
            if end < len(text):
                for sep in [". ", "\n\n", "\n", " "]:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > CHUNK_SIZE // 2:
                        end = start + last_sep + len(sep)
                        break

            chunks.append(text[start:end].strip())
            start = end - CHUNK_OVERLAP

        return [c for c in chunks if c]

    async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI's embedding API."""
        if not settings.OPENAI_API_KEY:
            raise EmbeddingError("OpenAI API key not configured for embeddings")

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts,
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )
            return [item.embedding for item in response.data]

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings: {e}")


# Singleton
knowledge_service = KnowledgeService()
