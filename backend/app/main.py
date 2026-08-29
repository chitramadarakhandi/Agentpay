"""AgentPay — Trusted AI-to-AI Commerce Platform.

FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_middleware import RequestTracingMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — init DB on startup."""
    # Startup: create tables (dev mode). In production, use Alembic.
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="AgentPay API",
    description="Trusted AI-to-AI Commerce Infrastructure with Enterprise Payment Safety",
    version="1.1.0",
    lifespan=lifespan,
)

# Request Tracing & Structured Logging Middleware
app.add_middleware(RequestTracingMiddleware)

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Import and register routes
from app.api.routes import buyer, merchants, orders, payments, policy, audit, analytics, demo, reconciliation, refunds, webhooks, subscriptions, split_payments  # noqa: E402

app.include_router(buyer.router, prefix="/api/buyer", tags=["buyer"])
app.include_router(merchants.router, prefix="/api/merchants", tags=["merchants"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(policy.router, prefix="/api/policy", tags=["policy"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(demo.router, prefix="/api/demo", tags=["demo"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["reconciliation"])
app.include_router(refunds.router, prefix="/api/refunds", tags=["refunds"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(split_payments.router, prefix="/api/split-payments", tags=["split-payments"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.1.0",
        "razorpay_configured": settings.razorpay_configured,
        "llm_configured": settings.llm_configured,
        "llm_provider": settings.llm_provider if settings.llm_configured else "none",
        "features": {
            "circuit_breaker": True,
            "rate_limiter": True,
            "idempotency_with_ttl": True,
            "dual_verification_convergence": True,
            "reconciliation_engine": True,
            "request_tracing": True,
            "realtime_refunds": True,
            "refund_sse_streaming": True,
            "ai_refund_agents": True,
            "refund_state_machine": True,
            "agent_autopay_subscriptions": True,
            "razorpay_route_split_payments": True,
            "red_team_playground": True,
        }
    }
