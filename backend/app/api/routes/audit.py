"""Audit trail routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.audit.audit_service import AuditService

router = APIRouter()


@router.get("/sessions/recent")
async def list_recent_sessions(db: AsyncSession = Depends(get_db)):
    """List recent unique session IDs with summary metadata."""
    audit = AuditService(db)
    sessions = await audit.get_recent_sessions(limit=20)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}")
async def get_audit_trail(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get full audit trail for a session."""
    audit = AuditService(db)
    trail = await audit.get_session_trail(session_id)
    return trail


@router.get("/{session_id}/chain")
async def get_audit_chain(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get the normalized transaction kill chain for a session."""
    audit = AuditService(db)
    return await audit.get_session_chain(session_id)


@router.get("")
async def list_audit_events(db: AsyncSession = Depends(get_db)):
    """List recent audit events across all sessions."""
    audit = AuditService(db)
    logs = await audit.get_recent_logs(limit=100)
    return {"audit_logs": logs, "count": len(logs)}
