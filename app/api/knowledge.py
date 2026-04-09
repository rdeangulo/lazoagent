"""Lazo Agent — Knowledge Base Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models import KnowledgeDocument
from app.models.knowledge import DocumentStatus
from app.schemas.knowledge import DocumentUploadRequest, SearchRequest
from app.services.knowledge_service import knowledge_service

router = APIRouter()


@router.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """List knowledge base documents."""
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    if status:
        stmt = stmt.where(KnowledgeDocument.status == DocumentStatus(status))
    if doc_type:
        stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    result = await db.execute(stmt.offset(offset).limit(limit))
    docs = result.scalars().all()

    return {
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "description": d.description,
                "doc_type": d.doc_type.value,
                "status": d.status.value,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in docs
        ],
        "total": total,
    }


@router.post("/documents")
async def upload_document(
    request: DocumentUploadRequest,
    admin: dict = Depends(get_current_admin),
):
    """Upload a new document to the knowledge base."""
    result = await knowledge_service.upload_document(
        title=request.title,
        content=request.content,
        doc_type=request.doc_type,
        description=request.description,
        uploaded_by_id=admin.get("sub"),
    )
    return result


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Delete a document and its chunks."""
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(doc)
    await db.commit()
    return {"deleted": True}


@router.post("/search")
async def search_knowledge(
    request: SearchRequest,
    admin: dict = Depends(get_current_admin),
):
    """Search the knowledge base (same as AI tool, for CRM use)."""
    results = await knowledge_service.search(
        query=request.query,
        doc_type=request.doc_type,
        limit=request.limit,
    )
    return {"results": results, "query": request.query}
