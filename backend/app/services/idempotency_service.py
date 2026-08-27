"""Idempotency Service — enforces distributed single-execution semantics with 24-hour TTL."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Tuple, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException, status

from app.models.idempotency import IdempotencyRecord, utcnow


class IdempotencyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def compute_hash(endpoint: str, payload: Any) -> str:
        """Generate SHA-256 fingerprint from endpoint path and normalized request payload."""
        data_str = f"{endpoint}:{json.dumps(payload, sort_keys=True, default=str)}"
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    async def check_and_start(
        self, idempotency_key: str, endpoint: str, payload: Any
    ) -> Optional[Tuple[int, Dict[str, Any]]]:
        """Check if request was already processed.
        
        Returns:
            - None: If key is new (a PENDING record has been saved, caller should execute business logic).
            - (status_code, response_body): If request was already completed, replay cached response.
            
        Raises:
            - HTTPException(409): If identical key is currently PENDING (in-flight request).
            - HTTPException(422): If key was used previously with different payload.
        """
        if not idempotency_key:
            return None

        req_hash = self.compute_hash(endpoint, payload)
        now = utcnow()

        # Query existing record
        result = await self.db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)
        )
        record = result.scalar_one_or_none()

        if record:
            # Check for TTL expiry
            # Ensure timezone awareness compatibility
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
                
            if expires_at < now:
                # Key expired: remove expired record and treat as new
                await self.db.delete(record)
                await self.db.flush()
            else:
                # Key is active
                if record.request_hash != req_hash:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Idempotency-Key reuse with altered request payload is not allowed.",
                    )

                if record.status == "PENDING":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A request with this Idempotency-Key is currently being processed. Please retry shortly.",
                    )

                if record.status == "COMPLETED":
                    # Replay cached response
                    return record.response_code, record.response_body

        # New or expired key: record PENDING state
        new_record = IdempotencyRecord(
            key=idempotency_key,
            request_hash=req_hash,
            status="PENDING",
        )
        self.db.add(new_record)
        await self.db.flush()
        return None

    async def complete(
        self, idempotency_key: str, response_code: int, response_body: Dict[str, Any]
    ):
        """Mark idempotency record as COMPLETED and cache response."""
        if not idempotency_key:
            return

        result = await self.db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = "COMPLETED"
            record.response_code = response_code
            record.response_body = response_body
            await self.db.flush()

    async def fail(self, idempotency_key: str):
        """Mark idempotency record as FAILED if operation encounters error."""
        if not idempotency_key:
            return

        result = await self.db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.key == idempotency_key)
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = "FAILED"
            await self.db.flush()

    async def purge_expired(self) -> int:
        """Purge all expired idempotency records (maintenance job)."""
        now = utcnow()
        result = await self.db.execute(
            delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < now)
        )
        return result.rowcount
