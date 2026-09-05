# AICB (AI Conversational Business Bot Engine)

A modular, lightweight, and production-ready AI & Interactive Step Chatbot engine designed for WhatsApp Cloud API, Telegram, and an embeddable Website Widget, with Conversational Commerce powered by Paystack and Bumpa.

---

## Architecture & Deployment

AICB runs as a standalone, autonomous conversational commerce hub with a built-in Single-Page Admin UI at **`/_/admin`**, paired seamlessly with [AgentOS](https://agentos.aicb.sannex.ng) for documentation, official releases, and telemetry.

### 1. Standalone Multi-Agent Instance

A single AICB instance runs its own complete admin studio at **`/_/admin`**, backed entirely by its database (SQLite in development, PostgreSQL in production):

- **First-Run Onboarding (`/_/admin/setup`)**: Instantly creates the Super Admin account and business profile with store currency and brand assets.
- **Multi-Agent Studio (`/_/admin/agents`)**: Deploy multiple distinct AI personas on the same deployment. Each agent can configure its own system prompt, LLM provider (Google Gemini, OpenAI, Groq, Anthropic), model parameters, access groups, and messaging channel credentials.
- **Messaging Channels**:
  - **WhatsApp Cloud API**: Interactive buttons, list pickers, carousels, and encrypted Meta flows.
  - **Telegram Bot**: Automated webhook registration upon agent creation, inline secret token rotators, and interactive keyboards.
  - **Website Widget**: Embeddable single-line script tag (`<script src="https://aicb.sannex.ng/widget.js" data-bot-id="default" async></script>`).
- **Unified Commerce & Payments**: Direct integration with **Paystack** for automated checkout generation and instant order confirmations across conversations.
- **Knowledge Base (RAG) & Catalog**: In-process hybrid BM25 + vector search and catalog scoping via access tags and access groups.
- **Platform API Keys**: One-click generation and instant rotation for secure programmatic API access (`aicb_live_...`).

### 2. Sannex AgentOS Hub Integration

- **Releases & Documentation**: Release notes and updates are fetched directly from the open-source AgentOS hub (`https://agentos.aicb.sannex.ng/releases`) and rendered within AICB's floating sidebar releases drawer.
- **Telemetry & Feedback**: Asynchronous background telemetry powered by the `sannex-agent` SDK.

---

## Key Features

1. **Messaging Channels**:
   - **WhatsApp Cloud API**: Text messages, Quick-Reply Interactive Buttons, List Pickers, Interactive Media Carousels, and Interactive WhatsApp Flows.
   - **Telegram**: Text messages, Inline Keyboards, automatic webhook synchronization (`setWebhook`), and in-place secret token rotators.
   - **Website Widget**: Lightweight embeddable chat widget with product card browsing, responsive drawer, dark/light theme, and direct checkout handoff.
   - **Slack Escalation**: Seamless handoff to human agents via Slack incoming webhooks.

2. **Multi-LLM Provider Engine**:
   - Out-of-the-box support for **Google Gemini**, **OpenAI GPT**, **Groq**, and **Anthropic Claude**.
   - Model parameters (`temperature`, `model_name`, `max_tokens`, `system_prompt`) configured per agent.
   - Per-agent API key overrides or centralized `.env` fallback.

3. **Multi-Source Catalog & Knowledge Base (RAG)**:
   - Synchronizes products from **Paystack Products**, **Bumpa Store**, or local database.
   - Smart multi-word keyword ranking (`CatalogManager.search_products`).
   - Access-group tagging for restricted product visibility across specific agents.
   - Grounded RAG document ingestion for accurate business FAQs and policies.

4. **Paystack Payment Gateway**:
   - Generates secure, instant checkout links and handles webhook events (`/api/v1/payments/webhook/paystack`).
   - Multi-currency support (`NGN`, `USD`, `GHS`, `KES`, `ZAR`, `EUR`, `GBP`).
   - Automatic order status confirmation and real-time customer messaging notifications upon payment receipt.

5. **Customer Profiles & Order Tracking**:
   - Pre-checkout customer detail collection (Name, Email, Phone).
   - "My Purchases" and order status lookup directly from chat conversations.
   - Customer directory in Admin UI with lifetime value and order history.

6. **Interactive Overview & Setup Guide**:
   - Onboarding milestone checklist on the dashboard overview (`/_/admin/overview`) with real-time completion tracking.
   - Multi-Agent Studio empty state with instant agent creation wizards.

---

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Configure DATABASE_URL, APP_SECRET, and optional SANNEX_API_KEY
```

### 2. Run Pre-flight System Doctor
```bash
python doctor.py
```

### 3. Start Local Server
```bash
# Using Python / Uvicorn
uvicorn app.main:app --port 8422 --reload

# Or using Docker Compose
docker compose up -d
```

### 4. First Run Onboarding
Open [http://localhost:8422/_/admin](http://localhost:8422/_/admin) to complete the setup wizard and launch your AI agents.

Open [http://localhost:8422/docs](http://localhost:8422/docs) to explore the interactive OpenAPI documentation.

---

## Webhook & API Endpoints

| Service | Endpoint | Method |
| :--- | :--- | :--- |
| **WhatsApp Cloud API** | `/api/v1/webhooks/whatsapp` | `GET` (Challenge), `POST` (Updates) |
| **Telegram Bot API** | `/api/v1/webhooks/telegram` or `/api/v1/webhooks/telegram/{agent_id}` | `POST` (Updates & Commands) |
| **Paystack Webhook** | `/api/v1/payments/webhook/paystack` | `POST` (Charge events) |
| **Bumpa Webhook** | `/api/v1/webhooks/bumpa` | `POST` (Product/Order updates) |
| **Manual Releases Sync** | `/api/v1/sync` | `POST` (Triggers AgentOS release sync) |
| **Setup Wizard** | `/api/v1/setup/status`, `/api/v1/setup/initialize` | `GET`, `POST` (First-run onboarding) |
| **Admin Auth** | `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/logout` | `POST`, `GET`, `POST` |
| **Multi-Agent CRUD** | `/api/v1/agents` | `GET`, `POST`, `PUT /{id}`, `DELETE /{id}` |
| **Access Groups** | `/api/v1/access-groups` | `GET`, `POST`, `PUT /{id}`, `DELETE /{id}` |
| **Team Accounts** | `/api/v1/users` | `GET`, `POST`, `PUT /{id}`, `DELETE /{id}` |
| **Platform Settings** | `/api/v1/settings/profile`, `/api/v1/settings/payments` | `GET`, `PUT` |
| **Admin Dashboard UI** | `/_/admin` | `GET` (SPA) |

---

## Project Structure

```text
aicb/
├── app/
│   ├── main.py                     # FastAPI application & lifespan
│   ├── admin_ui/                   # Standalone Admin SPA (served at /_/admin)
│   │   └── dist/js/pages/          # Overview, Agents, Catalog, RAG, Orders, Users, Settings
│   ├── api/                        # REST APIs (setup, auth, users, agents, access groups, settings, overview)
│   ├── core/                       # Config, database, security (JWT, platform keys, webhook verifiers)
│   ├── channels/                   # WhatsApp, Telegram, Slack, Website Widget handlers
│   ├── commerce/                   # CartManager, Catalog & Paystack integration, image storage
│   ├── ai/                         # Multi-LLM providers (Gemini, OpenAI, Groq, Claude), RAG & memory
│   ├── flows/                      # Deterministic 0-token fast-path conversational engine
│   ├── telemetry/                  # Sannex telemetry dispatcher & release sync worker
│   └── models/                     # SQLAlchemy models (Customer, Order, CatalogItem, BusinessProfile, AdminUser, Agent, AccessGroup)
├── widget/                         # Embeddable website chat widget (Vite, builds to widget.js)
├── doctor.py                       # Pre-flight diagnostic tool
├── Dockerfile                      # Production container image
├── docker-compose.yml              # Local development compose (port 8422)
├── docker-compose.prod.yml         # Production deployment stack
├── requirements.txt
└── .env.example
```

---

## Authentication Model

| Mechanism | Direction | Used for | Configured via |
| :--- | :--- | :--- | :--- |
| `aicb_live_...` platform key | External caller → AICB API | Programmatic API access | Generated and rotated from `/_/admin/settings` |
| Admin JWT session | Browser → AICB Admin | `/_/admin` dashboard sessions | Signed with `APP_SECRET`, issued by `/api/v1/auth/login` |
| `SANNEX_API_KEY` | AICB → AgentOS | Telemetry & Release Notes synchronization | `.env` |
| Webhook Secrets | Provider → AICB | Meta, Telegram & Paystack verification | Verified cryptographically with rotation support |
