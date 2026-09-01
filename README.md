# AICB (AI Conversational Business Bot Engine)

A modular, lightweight, and production-ready AI & Interactive Step Chatbot engine designed for WhatsApp Cloud API, Telegram, Slack, and Unified Commerce (Bumpa, Paystack, Flutterwave, Monnify, Stripe).

---

## Key Features

1. **Multi-Channel Interaction**:
   - **WhatsApp Cloud API**: Text messages, Quick-Reply Interactive Buttons, List Pickers, Interactive Flows (`flow_crypto.py` with RSA/AES encryption).
   - **Telegram**: Text messages, Inline Keyboards, Telegram MiniApp WebViews, and Native In-App Invoices.
   - **Slack & Fallback**: Human escalation dispatch to Slack webhooks, and automated customer support contact cards.

2. **Multi-LLM Provider Engine**:
   - Out-of-the-box support for **Google Gemini**, **OpenAI GPT**, and **Anthropic Claude**.
   - API keys configured in `.env`, while runtime parameters (`temperature`, `model_name`, `max_tokens`, `system_prompt`) are dynamically synchronized from **AgentOS** without needing server restarts.

3. **Multi-Source Catalog Manager**:
   - Syncs and serves product/service catalogs from:
     - **Paystack Products API** (`/product`)
     - **Bumpa E-Commerce Store** (`/products`)
     - **AgentOS / Local Database**

4. **Unified Payment Gateway**:
   - Generates checkout links and processes webhooks for **Paystack**, **Flutterwave**, **Monnify**, and **Stripe**.
   - Automatically confirms orders upon payment receipt and notifies customers across WhatsApp or Telegram.

5. **Self-Contained RAG & Memory**:
   - In-process hybrid BM25 and vector similarity search over business knowledge documents and FAQs.
   - Sliding-window conversation memory with configurable TTL auto-expiry (`SESSION_EXPIRY_HOURS`).

6. **Sannex Agent Telemetry & 12h Sync Worker**:
   - Asynchronous fire-and-forget telemetry queue with zero latency overhead.
   - Automatic 12-hour background synchronization (plus manual `POST /api/v1/sync`) to pull updated prompts, catalogs, and knowledge bases from AgentOS.

---

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Run Pre-flight System Doctor
```bash
python doctor.py
```

### 3. Start Local Server
```bash
# Using Python / Uvicorn
uvicorn app.main:app --port 8000 --reload

# Or using Docker Compose
docker compose up -d
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) to explore the interactive OpenAPI documentation.

---

## Webhook Endpoints

| Service | Endpoint | Method |
| :--- | :--- | :--- |
| **WhatsApp Cloud API** | `/api/v1/webhooks/whatsapp` | `GET` (Challenge), `POST` (Updates) |
| **Telegram Bot API** | `/api/v1/webhooks/telegram` | `POST` (Updates & Payments) |
| **Paystack** | `/api/v1/webhooks/payments/paystack` | `POST` (Charge events) |
| **Flutterwave** | `/api/v1/webhooks/payments/flutterwave` | `POST` (Charge events) |
| **Monnify** | `/api/v1/webhooks/payments/monnify` | `POST` (Transaction events) |
| **Stripe** | `/api/v1/webhooks/payments/stripe` | `POST` (Checkout completed) |
| **Bumpa** | `/api/v1/webhooks/bumpa` | `POST` (Product/Order updates) |
| **Manual Sync** | `/api/v1/sync` | `POST` (Triggers AgentOS sync) |

---

## Project Structure

```text
aicb/
├── app/
│   ├── main.py                     # FastAPI application & lifespan
│   ├── core/                       # Config, database, security, logger
│   ├── channels/                   # WhatsApp, Telegram, Slack
│   ├── commerce/                   # Unified catalog & payments (Paystack, Flutterwave, Monnify, Stripe, Bumpa)
│   ├── ai/                         # Multi-LLM providers (Gemini, OpenAI, Claude), prompts, memory, RAG, tools
│   ├── flows/                      # Deterministic interactive button engine & definitions
│   ├── telemetry/                  # Sannex telemetry dispatcher & 12h sync worker
│   └── models/                     # SQLAlchemy models
├── doctor.py                       # Pre-flight diagnostic tool
├── Dockerfile                      # Production container image
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
