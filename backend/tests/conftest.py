"""Pytest configuration and shared fixtures."""

import asyncio
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # Ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.main import app
from app.api.deps import get_db
from app.models.user import User, BuyerProfile
from app.models.merchant import Merchant, MerchantPolicy
from app.models.product import Product, Quote
from app.core.rate_limiter import payment_create_limiter, payment_verify_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset rate limiters between tests for isolation."""
    payment_create_limiter.buckets.clear()
    payment_verify_limiter.buckets.clear()
    yield
    payment_create_limiter.buckets.clear()
    payment_verify_limiter.buckets.clear()


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Create an HTTP test client bound to test database session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    """Seed test merchant, product, user, and active quote."""
    # 1. User & Profile
    user = User(
        id="demo-user-001",
        name="Test User",
        email="test@agentpay.ai",
    )
    db_session.add(user)

    profile = BuyerProfile(
        id="profile-001",
        user_id=user.id,
        daily_spending_limit=150000.0,
        single_transaction_limit=80000.0,
        requires_approval_above=50000.0,
        daily_spent=0.0,
        allowed_categories={"categories": ["electronics", "laptops", "phones"]},
        status="active",
    )
    db_session.add(profile)

    # 2. Merchant & Policy
    merchant = Merchant(
        id="merchant-tech-01",
        name="TechNova India",
        description="Premium tech products",
        category="electronics",
        trust_score=94.5,
        status="active",
    )
    db_session.add(merchant)

    policy = MerchantPolicy(
        id="policy-tech-01",
        merchant_id=merchant.id,
        max_discount_percent=15.0,
        auto_discount_percent=5.0,
        negotiation_enabled=True,
        min_order_value=500.0,
        requires_merchant_approval_above=100000.0,
    )
    db_session.add(policy)

    # 3. Product
    product = Product(
        id="prod-laptop-01",
        merchant_id=merchant.id,
        name="TechNova Pro 16",
        description="High performance laptop",
        category="laptops",
        price=75000.0,
        currency="INR",
        stock=10,
        rating=4.8,
        active=True,
    )
    db_session.add(product)

    # 4. Active Quote
    quote = Quote(
        id="quote-test-01",
        merchant_id=merchant.id,
        product_id=product.id,
        session_id="session-test-123",
        original_price=75000.0,
        discount_percent=10.0,
        discount_amount=7500.0,
        final_price=67500.0,
        valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
        status="active",
    )
    db_session.add(quote)

    await db_session.commit()
    return {
        "user": user,
        "profile": profile,
        "merchant": merchant,
        "product": product,
        "quote": quote,
    }
