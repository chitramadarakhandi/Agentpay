"""Audit service — immutable audit trail for all financially-relevant actions."""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.audit import AgentAction, AuditLog, PolicyViolation


class AuditService:
    """Records and queries audit trail entries.
    
    Every important action is recorded:
    - Agent decisions
    - Policy evaluations
    - Payment events
    - User approvals
    - Failures and violations
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        session_id: str,
        actor: str,
        action: str,
        reason: str = None,
        amount: float = None,
        policy_result: dict = None,
        approval_status: str = None,
        metadata: dict = None,
    ) -> AuditLog:
        """Record an audit log entry."""
        entry = AuditLog(
            id=str(uuid.uuid4()),
            session_id=session_id,
            actor=actor,
            action=action,
            reason=reason,
            amount=amount,
            policy_result=policy_result,
            approval_status=approval_status,
            metadata_json=metadata,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def log_agent_action(
        self,
        session_id: str,
        agent_type: str,
        action_type: str,
        input_data: dict = None,
        output_data: dict = None,
        status: str = "success",
        duration_ms: int = None,
        error_message: str = None,
    ) -> AgentAction:
        """Record an agent action."""
        entry = AgentAction(
            id=str(uuid.uuid4()),
            session_id=session_id,
            agent_type=agent_type,
            action_type=action_type,
            input_data=input_data,
            output_data=output_data,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def log_policy_violation(
        self,
        session_id: str,
        policy_type: str,
        requested_value: str,
        allowed_value: str,
        reason: str,
        severity: str = "medium",
    ) -> PolicyViolation:
        """Record a policy violation."""
        entry = PolicyViolation(
            id=str(uuid.uuid4()),
            session_id=session_id,
            policy_type=policy_type,
            requested_value=str(requested_value),
            allowed_value=str(allowed_value),
            reason=reason,
            severity=severity,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_session_trail(self, session_id: str) -> dict:
        """Get complete audit trail for a session."""
        # Audit logs
        logs_result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.session_id == session_id)
            .order_by(AuditLog.timestamp)
        )
        logs = logs_result.scalars().all()

        # Agent actions
        actions_result = await self.db.execute(
            select(AgentAction)
            .where(AgentAction.session_id == session_id)
            .order_by(AgentAction.created_at)
        )
        actions = actions_result.scalars().all()

        # Policy violations
        violations_result = await self.db.execute(
            select(PolicyViolation)
            .where(PolicyViolation.session_id == session_id)
            .order_by(PolicyViolation.created_at)
        )
        violations = violations_result.scalars().all()

        return {
            "session_id": session_id,
            "audit_logs": [
                {
                    "id": l.id,
                    "actor": l.actor,
                    "action": l.action,
                    "reason": l.reason,
                    "amount": l.amount,
                    "policy_result": l.policy_result,
                    "approval_status": l.approval_status,
                    "metadata": l.metadata_json,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                }
                for l in logs
            ],
            "agent_actions": [
                {
                    "id": a.id,
                    "agent_type": a.agent_type,
                    "action_type": a.action_type,
                    "input_data": a.input_data,
                    "output_data": a.output_data,
                    "status": a.status,
                    "duration_ms": a.duration_ms,
                    "error_message": a.error_message,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in actions
            ],
            "policy_violations": [
                {
                    "id": v.id,
                    "policy_type": v.policy_type,
                    "requested_value": v.requested_value,
                    "allowed_value": v.allowed_value,
                    "reason": v.reason,
                    "severity": v.severity,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in violations
            ],
            "total_events": len(logs) + len(actions) + len(violations),
        }

    async def get_session_chain(self, session_id: str) -> dict:
        """Return the normalized ten-stage transaction kill chain."""
        trail = await self.get_session_trail(session_id)
        events = [
            {**event, "event_kind": "audit"}
            for event in trail["audit_logs"]
        ] + [
            {**event, "event_kind": "agent"}
            for event in trail["agent_actions"]
        ]

        stage_specs = [
            ("request", "Request", ("request_submitted",)),
            ("parse", "Parse", ("parse_requirements",)),
            ("filter", "Filter", ("products_filtered_and_ranked", "filter_and_rank")),
            ("rank", "Rank", ("products_filtered_and_ranked", "filter_and_rank")),
            ("quote", "Quote", ("quote_generated", "quote_created")),
            ("negotiate", "Negotiate", ("negotiation_completed", "negotiation_blocked")),
            ("policy", "Policy Check", ("policy_check", "policy_evaluated", "policy_blocked")),
            ("approval", "Approval", ("order_created", "order_pending_approval", "order_human_approved", "order_human_rejected")),
            ("payment", "Payment", ("payment_intent_created",)),
            ("verified", "Verified", ("payment_verified_and_settled",)),
        ]

        def event_name(event: dict) -> str:
            return event.get("action") or event.get("action_type") or ""

        def is_blocked(event: dict) -> bool:
            status = str(event.get("status", "")).lower()
            approval = str(event.get("approval_status", "")).lower()
            policy_result = event.get("policy_result") or {}
            return (
                status in {"blocked", "failed", "rejected", "security_violation"}
                or approval in {"rejected", "blocked"}
                or policy_result.get("blocked") is True
            )

        stages = []
        stop_index = None
        for index, (key, name, names) in enumerate(stage_specs):
            matches = [event for event in events if event_name(event) in names]
            event = matches[-1] if matches else None
            if stop_index is not None:
                status = "unreached"
                reason = "Not reached because an earlier stage stopped the transaction."
            elif event is None:
                status = "unreached"
                reason = None
            elif is_blocked(event):
                status = "blocked"
                reason = event.get("reason") or event.get("error_message")
                stop_index = index
            elif event.get("approval_status") in {"pending", "pending_human_review"}:
                status = "pending"
                reason = event.get("reason")
                stop_index = index
            else:
                status = "passed"
                reason = event.get("reason") or event.get("error_message")

            detail = event.get("policy_result") if event else None
            metadata = event.get("metadata") or event.get("output_data") if event else None
            stages.append({
                "id": key,
                "name": name,
                "status": status,
                "reason": reason,
                "event": event,
                "policy_result": detail,
                "metadata": metadata,
            })

        stopping_stage = stages[stop_index] if stop_index is not None else None
        return {
            "session_id": session_id,
            "stages": stages,
            "status": stopping_stage["status"] if stopping_stage else ("passed" if events else "unreached"),
            "stopping_stage": stopping_stage["id"] if stopping_stage else None,
            "stop_reason": stopping_stage["reason"] if stopping_stage else None,
            "total_events": trail["total_events"],
        }

    async def get_recent_sessions(self, limit: int = 20) -> list[dict]:
        """Get unique recent sessions with summary metadata."""
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
        )
        logs = result.scalars().all()
        seen = set()
        sessions = []
        for l in logs:
            if l.session_id and l.session_id not in seen:
                seen.add(l.session_id)
                sessions.append({
                    "session_id": l.session_id,
                    "last_action": l.action,
                    "actor": l.actor,
                    "amount": l.amount,
                    "status": l.approval_status,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                })
                if len(sessions) >= limit:
                    break
        return sessions

    async def get_recent_logs(self, limit: int = 50) -> list[dict]:
        """Get recent audit logs across all sessions."""
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                "id": l.id,
                "session_id": l.session_id,
                "actor": l.actor,
                "action": l.action,
                "reason": l.reason,
                "amount": l.amount,
                "approval_status": l.approval_status,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            }
            for l in logs
        ]

    async def get_violations(self, limit: int = 50) -> list[dict]:
        """Get recent policy violations."""
        result = await self.db.execute(
            select(PolicyViolation)
            .order_by(PolicyViolation.created_at.desc())
            .limit(limit)
        )
        violations = result.scalars().all()
        return [
            {
                "id": v.id,
                "session_id": v.session_id,
                "policy_type": v.policy_type,
                "requested_value": v.requested_value,
                "allowed_value": v.allowed_value,
                "reason": v.reason,
                "severity": v.severity,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in violations
        ]
