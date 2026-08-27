# ⚡ AgentPay — Trusted AI-to-AI Agentic Commerce & Payment Safety Platform

> **Razorpay AI Buildathon (Track 01 — AI Growth & Agentic Commerce)**  
> Autonomous AI commerce infrastructure where buyer and merchant AI agents discover, negotiate, and execute Razorpay test transactions with deterministic policy governance and human approval gates.

---

## 🏛️ Key Architectural Principle
```
LLMs PROPOSE → Deterministic Backend DECIDES → Razorpay Gateway EXECUTES
```
LLMs are probabilistic actors. In enterprise payments, autonomous agents must operate within deterministic spending passports, dual-verification state convergence, idempotency locks, and human approval gates.

---

## ✨ Features & Capabilities

### 1. 🤖 Agent & Negotiation Layer
- **Discovery Agent:** Extracts requirements from natural language prompts, compares merchant catalogs, and matches top picks.
- **Autonomous Multi-Round Negotiation:** Evaluates volume discounts, bounded by merchant policies and anti-collusion guards.
- **Multi-LLM Support:** Compatible with Google Gemini, Groq, and OpenAI (with offline deterministic fallback).

### 2. 🛡️ Trust & Policy Engine (Safety First)
- **Spending Passport:** Configurable per-user single-transaction limits, daily allowances, and category permissions.
- **Human-in-the-Loop Approval Gates:** Orders exceeding `requires_approval_above` (e.g. ₹50,000) are assigned `status="pending_approval"` with cryptographic tokens (`secrets.token_urlsafe(24)`) and locked against payment until authorized in the Trust Center.
- **Explainable Arithmetic:** 100% deterministic deficit calculations ($Amount > Limit$).

### 3. 💳 Enterprise Payment & Resiliency Engine
- **Razorpay Test Mode Integration:** Order creation, signature verification, simulated webhooks, and refund flows.
- **Idempotency with 24h TTL:** SHA-256 request fingerprinting prevents duplicate orders or double-charges during agent retry loops.
- **Token Bucket Rate Limiter:** Thread-locked algorithm on sensitive endpoints (`/api/payments/create`, `/api/payments/verify`) returning `429 Too Many Requests`.
- **Double-Entry Reconciliation Engine:** Automated ledger auditing with auto-healing missed webhooks and strict money conservation invariant ($\sum \text{Orders} == \sum \text{Payments}$).

### 4. 📝 Immutable Audit Trail
- Chronological forensic event stream of every prompt, counter-offer, policy check, and gateway settlement.
- 1-click session lookup (`session_id`) to trace the complete agent reasoning history.
- **Audit chain API:** `GET /api/audit/{session_id}/chain` returns the normalized ten-stage security pipeline: Request, Parse, Filter, Rank, Quote, Negotiate, Policy Check, Approval, Payment, and Verified.
- **Kill-chain visualization:** The Audit Trail page renders live stage state as `passed`, `blocked`, `pending`, or `unreached`, with stopping reasons and responsive flow controls.
- **Explainability / Why?:** Reached stages expose decision details, policy data, arithmetic breakdowns, calculation values, reasons, and explainability scores when stored by the backend.
- **Human approval flow:** High-value orders stop at Approval until an authorized human approves or rejects the secure token-gated request.
- **Security controls:** Idempotency TTL, circuit breaker, rate limiting, reconciliation, money conservation, collusion detection, request tracing, and adversarial LLM safety checks remain enabled.

### 5. 🔗 Interactive Security Kill Chain and Explainability
- The Audit Trail renders the ten-stage journey: Request, Parse, Filter, Rank, Quote, Negotiate, Policy Check, Approval, Payment, and Verified.
- Stages use live data from `GET /api/audit/{session_id}/chain` and expose passed, blocked, pending, and unreached states.
- Selecting a stage opens its action, timestamp, trace ID, metadata, reason, and policy data. The **Why?** panel surfaces available arithmetic breakdowns and explainability scores without recreating backend decisions.

### 6. ↩️ Secure Refunds
- Refunds use the existing order, payment, audit, and gateway layers with the lifecycle `requested → validating → approved → processing → refunded` (or `rejected` / `failed`).
- `POST /api/refunds` supports full and partial refunds and requires an `Idempotency-Key`; `GET /api/refunds/{refund_id}` returns current status and remaining refundable balance.
- Validation prevents refunds for unpaid orders, invalid order/payment relationships, duplicate idempotency keys, concurrent over-refunds, and amounts above the remaining captured balance. Every lifecycle action is recorded in the session audit trail.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+

### 1. Backend Setup
```powershell
cd agentpay/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run migrations / seed initial catalog
python -m scripts.seed_data

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```
Backend API will be live at `http://localhost:8000` (Swagger docs at `http://localhost:8000/docs`).

### 2. Frontend Setup
```powershell
cd agentpay/frontend
npm install
npm run dev
```
Frontend Dashboard will be live at `http://localhost:5173`.

---

## 🧪 Running Tests

The test suite covers unit tests, integration tests, concurrency race-condition guards, and adversarial safety tests.

```powershell
cd agentpay/backend
.\venv\Scripts\pytest --cov=app --cov-report=term-missing tests/
```
**Test Results:** `53 passed (100% success rate)`

The current checkout does not contain the separately referenced `test_audit_chain.py`; the existing suite was rerun after the audit-chain implementation with `47 passed`. The frontend was verified with `npm run build` from `frontend/`.

---

## 📂 Project Structure
```text
agentpay/
├── backend/
│   ├── app/
│   │   ├── agents/          # Buyer, Merchant & Discovery agents
│   │   ├── api/routes/      # REST endpoints (orders, payments, policy, audit, demo)
│   │   ├── audit/           # Immutable audit logging service
│   │   ├── core/            # Config, DB engine, Rate limiter, Circuit breaker
│   │   ├── models/          # SQLAlchemy async database models
│   │   ├── payments/        # Razorpay integration & webhook handlers
│   │   ├── policies/        # TrustEngine, CollusionDetector, Spending Passport
│   │   └── services/        # OrderService, PaymentService, ReconciliationService
│   ├── scripts/             # Database seed scripts
│   └── tests/               # 47 unit & integration test suites
├── frontend/
│   ├── app.js               # Reactive SPA logic & API integrations
│   ├── index.html           # Dashboard layout
│   └── style.css            # Dark-mode design system
├── docker-compose.yml
└── README.md
```
