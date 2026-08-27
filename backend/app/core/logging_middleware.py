"""Structured Logging & Request Tracing Middleware.

Propagates X-Request-ID across all layers using contextvars and logs structured metadata.
"""

import time
import uuid
import contextvars
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable to hold the current request ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="req_system"
)

logger = logging.getLogger("agentpay.trace")


def get_current_request_id() -> str:
    """Retrieve the current request ID from context."""
    return request_id_var.get()


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns or propagates X-Request-ID and logs request life cycle."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract X-Request-ID from incoming headers, or generate a new trace ID
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id if incoming_id else f"req_{uuid.uuid4().hex[:12]}"
        
        token = request_id_var.set(req_id)
        start_time = time.perf_counter()

        logger.info(
            f"--> [REQ_START] {request.method} {request.url.path} | request_id={req_id} | client={request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            # Attach X-Request-ID header to outgoing response
            response.headers["X-Request-ID"] = req_id
            
            logger.info(
                f"<-- [REQ_END] {request.method} {request.url.path} | status={response.status_code} | duration={duration_ms}ms | request_id={req_id}"
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"<-- [REQ_ERROR] {request.method} {request.url.path} | error={str(exc)} | duration={duration_ms}ms | request_id={req_id}",
                exc_info=True,
            )
            raise exc
        finally:
            request_id_var.reset(token)
