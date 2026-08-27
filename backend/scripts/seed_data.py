"""Seed database with realistic test data.

5 merchants, 100+ products across categories, buyer profiles, and merchant policies.
Run: python -m scripts.seed_data
"""

import asyncio
import uuid
import random
from datetime import datetime, timezone

from app.core.database import async_session, init_db
from app.models.user import User, BuyerProfile
from app.models.merchant import Merchant, MerchantPolicy
from app.models.product import Product


def uid():
    return str(uuid.uuid4())


# ── Merchants ──────────────────────────────────────────────

MERCHANTS = [
    {
        "id": uid(),
        "name": "TechNova",
        "description": "Premium technology retailer specializing in high-performance computing and AI/ML hardware. Known for curated selection and expert support.",
        "category": "electronics",
        "trust_score": 4.7,
        "status": "active",
        "policy": {
            "max_discount_percent": 10.0,
            "min_order_value": 5000.0,
            "negotiation_enabled": True,
            "requires_merchant_approval_above": 150000.0,
            "auto_discount_percent": 3.0,
        },
    },
    {
        "id": uid(),
        "name": "ElectroMart",
        "description": "India's largest online electronics marketplace. Competitive prices, wide selection, and fast delivery across 500+ cities.",
        "category": "electronics",
        "trust_score": 4.3,
        "status": "active",
        "policy": {
            "max_discount_percent": 8.0,
            "min_order_value": 2000.0,
            "negotiation_enabled": True,
            "requires_merchant_approval_above": 100000.0,
            "auto_discount_percent": 2.0,
        },
    },
    {
        "id": uid(),
        "name": "ByteStore",
        "description": "Developer-focused hardware store. Specializes in workstations, GPUs, and development tools for software professionals.",
        "category": "electronics",
        "trust_score": 4.5,
        "status": "active",
        "policy": {
            "max_discount_percent": 12.0,
            "min_order_value": 10000.0,
            "negotiation_enabled": True,
            "requires_merchant_approval_above": 200000.0,
            "auto_discount_percent": 5.0,
        },
    },
    {
        "id": uid(),
        "name": "SmartHub",
        "description": "Smart devices and connected technology. From laptops to IoT devices, curated for the modern tech-savvy consumer.",
        "category": "electronics",
        "trust_score": 4.1,
        "status": "active",
        "policy": {
            "max_discount_percent": 7.0,
            "min_order_value": 3000.0,
            "negotiation_enabled": True,
            "requires_merchant_approval_above": 80000.0,
            "auto_discount_percent": 2.0,
        },
    },
    {
        "id": uid(),
        "name": "DigiWorld",
        "description": "Budget-friendly electronics with no compromise on quality. Best deals on refurbished and new tech products.",
        "category": "electronics",
        "trust_score": 3.9,
        "status": "active",
        "policy": {
            "max_discount_percent": 15.0,
            "min_order_value": 1000.0,
            "negotiation_enabled": True,
            "requires_merchant_approval_above": 50000.0,
            "auto_discount_percent": 4.0,
        },
    },
]


# ── Products ─────────────────────────────────────────────

def make_laptops(merchant_id: str, merchant_name: str) -> list[dict]:
    """Generate laptop products for a merchant."""
    base_laptops = [
        {
            "name": f"ProBook X1 ({merchant_name})",
            "description": "High-performance laptop for AI/ML development with dedicated GPU and fast NVMe storage.",
            "category": "laptops",
            "price": 74999.0,
            "stock": 15,
            "rating": 4.6,
            "delivery_days": 2,
            "specifications": {
                "processor": "Intel Core i7-13700H",
                "ram_gb": 16,
                "storage_gb": 512,
                "storage_type": "NVMe SSD",
                "gpu": "NVIDIA RTX 3050 4GB",
                "display": "15.6 inch FHD IPS",
                "battery_hours": 8,
                "os": "Windows 11 Pro",
                "weight_kg": 1.8,
            },
        },
        {
            "name": f"UltraBook Pro ({merchant_name})",
            "description": "Ultra-thin premium laptop with stunning display and all-day battery life.",
            "category": "laptops",
            "price": 89999.0,
            "stock": 8,
            "rating": 4.8,
            "delivery_days": 3,
            "specifications": {
                "processor": "Intel Core i7-1365U",
                "ram_gb": 16,
                "storage_gb": 1024,
                "storage_type": "NVMe SSD",
                "gpu": "Intel Iris Xe",
                "display": "14 inch 2.8K OLED",
                "battery_hours": 14,
                "os": "Windows 11 Pro",
                "weight_kg": 1.2,
            },
        },
        {
            "name": f"DevStation 15 ({merchant_name})",
            "description": "Developer workstation laptop with large RAM and powerful processor for compilation and containerization.",
            "category": "laptops",
            "price": 69999.0,
            "stock": 20,
            "rating": 4.4,
            "delivery_days": 2,
            "specifications": {
                "processor": "AMD Ryzen 7 7840HS",
                "ram_gb": 32,
                "storage_gb": 512,
                "storage_type": "NVMe SSD",
                "gpu": "AMD Radeon 780M",
                "display": "15.6 inch FHD IPS 144Hz",
                "battery_hours": 10,
                "os": "Windows 11 Pro",
                "weight_kg": 1.9,
            },
        },
        {
            "name": f"ML Powerhouse ({merchant_name})",
            "description": "Purpose-built for machine learning with high-end GPU and massive storage.",
            "category": "laptops",
            "price": 124999.0,
            "stock": 5,
            "rating": 4.9,
            "delivery_days": 4,
            "specifications": {
                "processor": "Intel Core i9-13900HX",
                "ram_gb": 32,
                "storage_gb": 1024,
                "storage_type": "NVMe SSD",
                "gpu": "NVIDIA RTX 4060 8GB",
                "display": "16 inch QHD+ IPS 165Hz",
                "battery_hours": 6,
                "os": "Windows 11 Pro",
                "weight_kg": 2.5,
            },
        },
        {
            "name": f"Budget Coder ({merchant_name})",
            "description": "Affordable laptop for students and entry-level developers.",
            "category": "laptops",
            "price": 42999.0,
            "stock": 30,
            "rating": 4.0,
            "delivery_days": 3,
            "specifications": {
                "processor": "AMD Ryzen 5 7530U",
                "ram_gb": 8,
                "storage_gb": 512,
                "storage_type": "NVMe SSD",
                "gpu": "AMD Radeon Graphics",
                "display": "15.6 inch FHD IPS",
                "battery_hours": 9,
                "os": "Windows 11 Home",
                "weight_kg": 1.7,
            },
        },
        {
            "name": f"AI Notebook 16 ({merchant_name})",
            "description": "16-inch laptop optimized for AI workloads with CUDA cores and fast memory.",
            "category": "laptops",
            "price": 79999.0,
            "stock": 12,
            "rating": 4.5,
            "delivery_days": 2,
            "specifications": {
                "processor": "Intel Core i7-13650HX",
                "ram_gb": 16,
                "storage_gb": 512,
                "storage_type": "NVMe SSD",
                "gpu": "NVIDIA RTX 3060 6GB",
                "display": "16 inch WQXGA IPS",
                "battery_hours": 7,
                "os": "Windows 11 Pro",
                "weight_kg": 2.1,
            },
        },
        # Intentionally over-budget to test filtering
        {
            "name": f"Creator Studio ({merchant_name})",
            "description": "Professional content creation workstation with color-accurate display.",
            "category": "laptops",
            "price": 159999.0,
            "stock": 3,
            "rating": 4.7,
            "delivery_days": 5,
            "specifications": {
                "processor": "Intel Core i9-13980HX",
                "ram_gb": 64,
                "storage_gb": 2048,
                "storage_type": "NVMe SSD",
                "gpu": "NVIDIA RTX 4070 8GB",
                "display": "16 inch 4K OLED",
                "battery_hours": 5,
                "os": "Windows 11 Pro",
                "weight_kg": 2.8,
            },
        },
        # Low RAM — should be filtered
        {
            "name": f"Slim Note ({merchant_name})",
            "description": "Ultra-portable slim notebook for basic tasks and travel.",
            "category": "laptops",
            "price": 34999.0,
            "stock": 25,
            "rating": 3.8,
            "delivery_days": 1,
            "specifications": {
                "processor": "Intel Core i3-1315U",
                "ram_gb": 8,
                "storage_gb": 256,
                "storage_type": "SSD",
                "gpu": "Intel UHD Graphics",
                "display": "14 inch FHD",
                "battery_hours": 12,
                "os": "Windows 11 Home S",
                "weight_kg": 1.3,
            },
        },
    ]

    products = []
    for laptop in base_laptops:
        # Vary prices slightly per merchant
        price_var = random.uniform(0.95, 1.05)
        laptop_copy = laptop.copy()
        laptop_copy["price"] = round(laptop_copy["price"] * price_var, 0)
        laptop_copy["merchant_id"] = merchant_id
        laptop_copy["id"] = uid()
        laptop_copy["currency"] = "INR"
        laptop_copy["active"] = True
        products.append(laptop_copy)

    return products


def make_phones(merchant_id: str, merchant_name: str) -> list[dict]:
    """Generate phone products."""
    phones = [
        {
            "name": f"FlagShip X ({merchant_name})",
            "description": "Premium flagship smartphone with pro-grade camera system.",
            "category": "phones",
            "price": 69999.0,
            "stock": 25,
            "rating": 4.6,
            "delivery_days": 1,
            "specifications": {
                "processor": "Snapdragon 8 Gen 3",
                "ram_gb": 12,
                "storage_gb": 256,
                "display": "6.7 inch AMOLED 120Hz",
                "battery_mah": 5000,
                "camera_mp": 200,
                "os": "Android 14",
            },
        },
        {
            "name": f"MidRange Pro ({merchant_name})",
            "description": "Best value mid-range phone with flagship-level features.",
            "category": "phones",
            "price": 24999.0,
            "stock": 50,
            "rating": 4.3,
            "delivery_days": 2,
            "specifications": {
                "processor": "Snapdragon 7 Gen 2",
                "ram_gb": 8,
                "storage_gb": 128,
                "display": "6.5 inch AMOLED 90Hz",
                "battery_mah": 5500,
                "camera_mp": 108,
                "os": "Android 14",
            },
        },
    ]

    products = []
    for phone in phones:
        price_var = random.uniform(0.97, 1.03)
        phone_copy = phone.copy()
        phone_copy["price"] = round(phone_copy["price"] * price_var, 0)
        phone_copy["merchant_id"] = merchant_id
        phone_copy["id"] = uid()
        phone_copy["currency"] = "INR"
        phone_copy["active"] = True
        products.append(phone_copy)

    return products


def make_accessories(merchant_id: str, merchant_name: str) -> list[dict]:
    """Generate accessory products."""
    accessories = [
        {
            "name": f"Mechanical Keyboard Pro ({merchant_name})",
            "description": "Hot-swappable mechanical keyboard with RGB backlighting.",
            "category": "accessories",
            "price": 5999.0,
            "stock": 40,
            "rating": 4.4,
            "delivery_days": 2,
            "specifications": {"type": "mechanical", "switches": "Cherry MX Brown", "connectivity": "USB-C + Bluetooth"},
        },
        {
            "name": f"27\" 4K Monitor ({merchant_name})",
            "description": "Professional 27-inch 4K IPS monitor for development and design.",
            "category": "accessories",
            "price": 32999.0,
            "stock": 10,
            "rating": 4.5,
            "delivery_days": 3,
            "specifications": {"size_inches": 27, "resolution": "3840x2160", "panel": "IPS", "refresh_rate": "60Hz"},
        },
        {
            "name": f"Wireless Mouse ({merchant_name})",
            "description": "Ergonomic wireless mouse with precision sensor.",
            "category": "accessories",
            "price": 2499.0,
            "stock": 60,
            "rating": 4.2,
            "delivery_days": 1,
            "specifications": {"type": "wireless", "dpi": 4000, "battery_months": 18},
        },
        {
            "name": f"USB-C Hub ({merchant_name})",
            "description": "12-in-1 USB-C hub with dual HDMI, Ethernet, and SD card reader.",
            "category": "accessories",
            "price": 3999.0,
            "stock": 35,
            "rating": 4.1,
            "delivery_days": 2,
            "specifications": {"ports": 12, "hdmi_count": 2, "ethernet": True, "pd_watts": 100},
        },
    ]

    products = []
    for acc in accessories:
        price_var = random.uniform(0.95, 1.05)
        acc_copy = acc.copy()
        acc_copy["price"] = round(acc_copy["price"] * price_var, 0)
        acc_copy["merchant_id"] = merchant_id
        acc_copy["id"] = uid()
        acc_copy["currency"] = "INR"
        acc_copy["active"] = True
        products.append(acc_copy)

    return products


# ── Demo Users ──────────────────────────────────────────

DEMO_USER = {
    "id": "demo-user-001",
    "name": "Demo User",
    "email": "demo@agentpay.dev",
}

DEMO_BUYER_PROFILE = {
    "id": "demo-profile-001",
    "user_id": "demo-user-001",
    "daily_spending_limit": 150000.0,
    "single_transaction_limit": 80000.0,
    "requires_approval_above": 50000.0,
    "allowed_categories": {"categories": ["electronics", "laptops", "phones", "accessories"]},
    "daily_spent": 0.0,
    "status": "active",
}


async def seed():
    """Populate the database with test data."""
    await init_db()

    async with async_session() as session:
        # Check if already seeded
        from sqlalchemy import select, func
        result = await session.execute(select(func.count()).select_from(Merchant))
        count = result.scalar()
        if count > 0:
            print(f"Database already seeded ({count} merchants). Skipping.")
            return

        print("[SEED] Seeding database...")

        # Create demo user
        user = User(**DEMO_USER)
        session.add(user)
        print(f"  [+] Created demo user: {DEMO_USER['name']}")

        # Create buyer profile
        profile = BuyerProfile(**DEMO_BUYER_PROFILE)
        session.add(profile)
        print(f"  [+] Created buyer profile (limit: Rs.{DEMO_BUYER_PROFILE['single_transaction_limit']:,.0f})")

        # Create merchants and products
        total_products = 0
        for m_data in MERCHANTS:
            policy_data = m_data.pop("policy")
            merchant = Merchant(**m_data)
            session.add(merchant)

            policy = MerchantPolicy(
                id=uid(),
                merchant_id=m_data["id"],
                allowed_categories={"categories": ["electronics", "laptops", "phones", "accessories"]},
                **policy_data,
            )
            session.add(policy)

            # Generate products
            products = []
            products.extend(make_laptops(m_data["id"], m_data["name"]))
            products.extend(make_phones(m_data["id"], m_data["name"]))
            products.extend(make_accessories(m_data["id"], m_data["name"]))

            # Some merchants may be out of stock on certain items
            for p_data in products:
                if random.random() < 0.05:  # 5% chance out of stock
                    p_data["stock"] = 0
                specs = p_data.pop("specifications")
                product = Product(specifications=specs, **p_data)
                session.add(product)
                total_products += 1

            print(f"  [+] {m_data['name']}: {len(products)} products (max discount: {policy_data['max_discount_percent']}%)")

        await session.flush()

        # Seed sample completed orders for immediate refund testing
        from app.models.order import Order
        from app.models.payment import Payment
        from app.models.product import Quote
        from datetime import timedelta

        now = datetime.now(timezone.utc)

        # Get first laptop product
        from sqlalchemy import select
        laptop = (await session.execute(select(Product).where(Product.category == "laptops"))).scalars().first()
        phone = (await session.execute(select(Product).where(Product.category == "phones"))).scalars().first()

        if laptop:
            # 1. Active eligible laptop order
            order_laptop = Order(
                id="order-laptop-demo-01",
                buyer_id="demo-user-001",
                merchant_id=laptop.merchant_id,
                product_id=laptop.id,
                session_id="session-demo-laptop-01",
                amount=laptop.price,
                currency="INR",
                status="success",
                created_at=now,
            )
            pay_laptop = Payment(
                id="pay-laptop-demo-01",
                order_id=order_laptop.id,
                razorpay_payment_id="pay_test_laptop_001",
                amount=laptop.price,
                currency="INR",
                status="success",
                created_at=now,
            )
            session.add_all([order_laptop, pay_laptop])

            # 2. Expired laptop order (purchased 20 days ago)
            past_date = now - timedelta(days=20)
            order_expired = Order(
                id="order-expired-demo-03",
                buyer_id="demo-user-001",
                merchant_id=laptop.merchant_id,
                product_id=laptop.id,
                session_id="session-demo-expired-03",
                amount=laptop.price,
                currency="INR",
                status="success",
                created_at=past_date,
            )
            pay_expired = Payment(
                id="pay-expired-demo-03",
                order_id=order_expired.id,
                razorpay_payment_id="pay_test_expired_003",
                amount=laptop.price,
                currency="INR",
                status="success",
                created_at=past_date,
            )
            session.add_all([order_expired, pay_expired])

        if phone:
            # 3. Active eligible phone order
            order_phone = Order(
                id="order-phone-demo-02",
                buyer_id="demo-user-001",
                merchant_id=phone.merchant_id,
                product_id=phone.id,
                session_id="session-demo-phone-02",
                amount=phone.price,
                currency="INR",
                status="success",
                created_at=now,
            )
            pay_phone = Payment(
                id="pay-phone-demo-02",
                order_id=order_phone.id,
                razorpay_payment_id="pay_test_phone_002",
                amount=phone.price,
                currency="INR",
                status="success",
                created_at=now,
            )
            session.add_all([order_phone, pay_phone])

        # Seed full 10-stage kill chain audit trail for session-demo-laptop-01 (Passed)
        from app.models.audit import AuditLog, AgentAction
        session_id_passed = "session-demo-laptop-01"
        stages_passed = [
            ("request_submitted", "buyer_agent", "Submitted natural language request for AI laptop.", 75000.0, "approved"),
            ("parse_requirements", "buyer_agent", "Extracted category: laptops, budget: Rs.80,000.", 75000.0, "approved"),
            ("products_filtered_and_ranked", "buyer_agent", "Filtered 14 products; ranked TechNova Pro 16 as top match.", 75000.0, "approved"),
            ("quote_generated", "merchant_agent", "TechNova issued Quote with 5% discount (Rs.71,250).", 71250.0, "approved"),
            ("negotiation_completed", "merchant_agent", "Autonomous negotiation reached consensus at Rs.71,250.", 71250.0, "approved"),
            ("policy_check", "policy_engine", "Single limit Rs.80,000 and Daily limit Rs.150,000 passed.", 71250.0, "approved"),
            ("order_created", "system", "Human approved transaction and created order.", 71250.0, "approved"),
            ("payment_intent_created", "payment_service", "Razorpay payment intent created.", 71250.0, "approved"),
            ("payment_verified_and_settled", "razorpay", "Dual convergence verified: signature valid and funds captured.", 71250.0, "approved"),
        ]
        for action, actor, reason, amt, status_val in stages_passed:
            session.add(AuditLog(
                id=str(uuid.uuid4()),
                session_id=session_id_passed,
                actor=actor,
                action=action,
                reason=reason,
                amount=amt,
                approval_status=status_val,
                policy_result={"allowed": True, "explainability_score": 98, "arithmetic_breakdown": ["Budget: Rs.80,000 >= Price: Rs.71,250", "Daily Limit: Rs.150,000 remaining"]},
                metadata_json={"request_id": f"req-{uuid.uuid4().hex[:8]}"},
                timestamp=now,
            ))

        # Seed kill chain for session-demo-expired-03 (Blocked at policy)
        session_id_blocked = "session-demo-expired-03"
        stages_blocked = [
            ("request_submitted", "buyer_agent", "User requested laptop purchase exceeding policy.", 200000.0, "approved"),
            ("parse_requirements", "buyer_agent", "Extracted budget: Rs.200,000.", 200000.0, "approved"),
            ("products_filtered_and_ranked", "buyer_agent", "Found high-end workstation.", 195000.0, "approved"),
            ("quote_generated", "merchant_agent", "Merchant issued quote at Rs.190,000.", 190000.0, "approved"),
            ("policy_check", "policy_engine", "BLOCKED: Amount Rs.190,000 exceeds single transaction limit Rs.80,000.", 190000.0, "rejected"),
        ]
        for action, actor, reason, amt, status_val in stages_blocked:
            session.add(AuditLog(
                id=str(uuid.uuid4()),
                session_id=session_id_blocked,
                actor=actor,
                action=action,
                reason=reason,
                amount=amt,
                approval_status=status_val,
                policy_result={"allowed": status_val == "approved", "blocked": status_val == "rejected", "explainability_score": 99, "arithmetic_breakdown": ["Deficit: Rs.190,000 > Single limit Rs.80,000 by Rs.110,000"]},
                metadata_json={"request_id": f"req-{uuid.uuid4().hex[:8]}"},
                timestamp=now,
            ))

        await session.commit()
        print(f"\n[OK] Seeded: {len(MERCHANTS)} merchants, {total_products} products")
        print(f"     Sample Orders ready for Refund & Kill Chain testing:")
        print(f"       * session-demo-laptop-01  (All 10 Stages PASSED)")
        print(f"       * session-demo-expired-03 (Stage 7 BLOCKED - Policy Violation)")
        print(f"     Demo user: {DEMO_USER['email']}")


if __name__ == "__main__":
    asyncio.run(seed())
