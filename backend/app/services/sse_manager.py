"""Server-Sent Events manager for real-time refund status updates.

Uses in-memory asyncio.Queue per subscriber. When a refund state changes,
the service publishes an event and all connected SSE clients receive the
update immediately.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

logger = logging.getLogger("agentpay.sse")


class SSEManager:
    """Manages SSE subscriptions for real-time refund updates."""

    def __init__(self):
        # refund_id -> set of asyncio.Queue
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, refund_id: str) -> asyncio.Queue:
        """Subscribe to updates for a specific refund. Returns a queue to read from."""
        if refund_id not in self._subscribers:
            self._subscribers[refund_id] = set()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[refund_id].add(queue)
        logger.info(f"[SSE] New subscriber for refund {refund_id}. Total: {len(self._subscribers[refund_id])}")
        return queue

    def unsubscribe(self, refund_id: str, queue: asyncio.Queue):
        """Remove a subscriber."""
        if refund_id in self._subscribers:
            self._subscribers[refund_id].discard(queue)
            if not self._subscribers[refund_id]:
                del self._subscribers[refund_id]
            logger.info(f"[SSE] Subscriber removed for refund {refund_id}.")

    async def publish(self, refund_id: str, event_type: str, data: dict[str, Any]):
        """Publish an event to all subscribers of a refund."""
        if refund_id not in self._subscribers:
            return

        payload = {
            "event": event_type,
            "refund_id": refund_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        dead_queues = []
        for queue in self._subscribers[refund_id]:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                dead_queues.append(queue)

        for q in dead_queues:
            self._subscribers[refund_id].discard(q)

        logger.info(f"[SSE] Published '{event_type}' for refund {refund_id} to {len(self._subscribers.get(refund_id, set()))} subscribers.")

    async def event_stream(self, refund_id: str) -> AsyncGenerator[str, None]:
        """Generate SSE-formatted event stream for a refund."""
        queue = self.subscribe(refund_id)
        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'refund_id': refund_id, 'message': 'Connected to refund stream'})}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['event']}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"event: keepalive\ndata: {json.dumps({'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
        finally:
            self.unsubscribe(refund_id, queue)


# Global singleton
refund_sse_manager = SSEManager()
