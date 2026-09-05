# AICB (AI Conversational Business Bot Engine)

A modular, lightweight, and production-ready AI & Interactive Step Chatbot engine designed for WhatsApp Cloud API, Telegram, and an embeddable Website Widget, with Unified Commerce (Bumpa, Paystack, Flutterwave, Monnify, Stripe).

---

## Two ways to run AICB

AICB supports two deployment modes on the exact same codebase — pick one per instance.

### 1. AgentOS-connected (one instance per bot)

The classic mode: one AICB instance is paired 1:1 with a bot managed from [AgentOS](https://agentos.aicb.sannex.ng)'s dashboard. AgentOS syncs the bot's system prompt, model settings, catalog, and knowledge base into AICB automatically every 30 minutes (and on-demand via `POST /api/v1/sync`) — you don't touch AICB's own config for day-to-day bot management. AICB authenticates itself to AgentOS with `SANNEX_API_KEY`; AgentOS authenticates its own calls back into AICB (catalog edits, image uploads, order lookups) with `AICB_API_KEY`, a shared secret you copy from that bot's Identity settings in AgentOS.

Channel credentials (WhatsApp/Telegram tokens) are set in AgentOS's own bot settings, not in AICB's `.env` — AgentOS syncs them down the same way it syncs the prompt and catalog.

### 2. Standalone (one instance per business, multiple agents)

For businesses that don't use AgentOS: a single AICB instance runs its own admin dashboard at **`/_/admin`**, backed entirely by its own database — no AgentOS required. On first boot, visiting `/_/admin` redirects to a one-time setup wizard (`/_/admin/setup`) that creates your Super Admin account and business profile; every other operation goes through `/_/admin/login` after that.

A standalone instance can run **multiple AI agents** at once, each with its own persona (`system_prompt`), model/provider/temperature, and its own independent WhatsApp/Telegram credentials — so one deployment can serve several distinct bots (e.g. a sales agent and a support agent) that share the same product catalog and knowledge base but see different slices of it via **access tags** and **access groups**. Incoming WhatsApp messages route to the right agent automatically by matching the message's `phone_number_id`; incoming Telegram messages route by the `/api/v1/webhooks/telegram/{agent_id}` path or by bot token.

The dashboard also holds a **Customers directory** (cross-channel order history and profiles) and **platform API key rotation** — the standalone equivalent of `AICB_API_KEY`, but platform-generated (`aicb_live_...`), hashed at rest, and rotatable with one click instead of a value you paste into `.env` yourself.

> **Status:** the standalone admin dashboard is newer and under active development — check `git log` on `app/api/`, `app/admin_ui/`, and `app/models/{business,user,agent,access_group}.py` before assuming a given screen is finished. The AgentOS-connected mode is the long-established, stable path.

### Which env vars matter for which mode

See the fully-commented [.env.example](.env.example) — every section is labeled with which mode it applies to. In short: **neither mode puts WhatsApp/Telegram tokens in `.env`** — they're always set per agent, in whichever dashboard you're using (standalone: `/_/admin`; AgentOS-connected: AgentOS itself). Infra-level settings (LLM provider keys, database, payments, image storage, webhook-level secrets like `META_APP_SECRET`) are shared by both modes and always come from `.env`.

---

## Key Features

1. **Multi-Channel Interaction**:
   - **WhatsApp Cloud API**: Text messages, Quick-Reply Interactive Buttons, List Pickers, a free-form Interactive Media Carousel for browsing multiple products (swipeable image cards, no Meta Commerce Catalog required), and Interactive Flows (`flow_crypto.py` with RSA/AES encryption).
   - **Telegram**: Text messages, Inline Keyboards, a swipeable product photo album (`sendMediaGroup`) for browsing multiple products, Native In-App Invoices, and **inline mode** (`@yourbot <search term>`, from any chat or via a switch-to-inline button in the current one) for quick product search.
   - **Website Widget**: Embeddable `<script>` chat widget with product cards, buttons, formatted (bold/italic/list) message rendering, an expand/collapse size toggle, and checkout handoff.
   - **Slack & Fallback**: Human escalation dispatch to Slack webhooks, and automated customer support contact cards.

2. **Multi-LLM Provider Engine**:
   - Out-of-the-box support for **Google Gemini**, **OpenAI GPT**, and **Anthropic Claude**.
   - In AgentOS-connected mode, runtime parameters (`temperature`, `model_name`, `max_tokens`, `system_prompt`) sync automatically from AgentOS with no server restart. In standalone mode, each Agent's settings live in AICB's own database and are edited directly in `/_/admin`.
   - Any agent can override the global API key with its own (`api_key_override`); otherwise it falls back to the matching `*_API_KEY` in `.env`.

3. **Multi-Source Catalog Manager**:
   - Syncs and serves product/service catalogs from:
     - **Paystack Products API** (`/product`)
     - **Bumpa E-Commerce Store** (`/products`)
     - **AgentOS / Local Database**
   - Flexible multi-word product search (`CatalogManager.search_products`) ranks by how many distinct query words match, not just substring — finds "Wireless Blue Earbuds Pro" for a query like "blue wireless earbuds" even out of order.
   - In standalone mode, catalog items and knowledge base docs can carry **access tags** so only agents with a matching tag (directly or via their access group) can see and recommend them; untagged items are public to every agent.

4. **Unified Payment Gateway**:
   - Generates checkout links and processes webhooks for **Paystack**, **Flutterwave**, **Monnify**, and **Stripe**.
   - Automatically confirms orders upon payment receipt and notifies customers across WhatsApp or Telegram.

5. **Customer Profiles & Pre-Checkout Collection**:
   - Collects Full Name, Email, and Phone before checkout (pre-filled from WhatsApp/Telegram profile data where possible, always asked fresh on the widget), timeboxed to 10 minutes of inactivity before auto-cancelling.
   - A standalone "My Profile" / "My Purchases" menu entry lets customers view/update their saved details and order history anytime, not just at checkout.

6. **Self-Contained RAG & Memory**:
   - In-process hybrid BM25 and vector similarity search over business knowledge documents and FAQs.
   - Sliding-window conversation memory with configurable TTL auto-expiry (`SESSION_EXPIRY_HOURS`).

7. **Sannex Agent Telemetry & 30m Sync Worker** *(AgentOS-connected mode)*:
   - Asynchronous fire-and-forget telemetry queue with zero latency overhead.
   - Automatic 30-minute background synchronization (plus manual `POST /api/v1/sync`) to pull updated prompts, catalogs, and knowledge bases from AgentOS.

8. **Product Image Storage** *(optional)*:
   - Cloudinary or Cloudflare R2 for product images, configured once in `.env` (shared across all agents on the instance). If left unconfigured, the product edit form simply won't ask for an image, and customers won't be sent a broken image link — everything else keeps working.

---

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env — see the comments in .env.example for what each mode needs
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

### 4. First run
- **Standalone mode:** open [http://localhost:8422/_/admin](http://localhost:8422/_/admin) — you'll be redirected to the setup wizard to create your Super Admin account, business profile, and first agent.
- **AgentOS-connected mode:** nothing to do here — make sure `AICB_API_KEY`/`SANNEX_API_KEY` are set, then manage the bot from AgentOS's dashboard as usual.

Open [http://localhost:8422/docs](http://localhost:8422/docs) to explore the interactive OpenAPI documentation.

---

## Webhook & API Endpoints

| Service | Endpoint | Method |
| :--- | :--- | :--- |
| **WhatsApp Cloud API** | `/api/v1/webhooks/whatsapp` | `GET` (Challenge), `POST` (Updates) |
| **Telegram Bot API** | `/api/v1/webhooks/telegram` or `/api/v1/webhooks/telegram/{agent_id}` | `POST` (Updates, Payments, Inline Queries) |
| **Paystack** | `/api/v1/webhooks/payments/paystack` | `POST` (Charge events) |
| **Flutterwave** | `/api/v1/webhooks/payments/flutterwave` | `POST` (Charge events) |
| **Monnify** | `/api/v1/webhooks/payments/monnify` | `POST` (Transaction events) |
| **Stripe** | `/api/v1/webhooks/payments/stripe` | `POST` (Checkout completed) |
| **Bumpa** | `/api/v1/webhooks/bumpa` | `POST` (Product/Order updates) |
| **Manual Sync** | `/api/v1/sync` | `POST` (Triggers AgentOS sync) |
| **Standalone Setup** | `/api/v1/setup/status`, `/api/v1/setup/initialize` | `GET`, `POST` (First-run onboarding) |
| **Standalone Admin Auth** | `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/logout` | `POST`, `GET`, `POST` |
| **Standalone Agents** | `/api/v1/agents` | `GET`, `POST`, `PUT /{id}`, `DELETE /{id}` |
| **Standalone Access Groups** | `/api/v1/access-groups` | `GET`, `POST`, `PUT /{id}`, `DELETE /{id}` |
| **Standalone Users** | `/api/v1/users` | `GET`, `POST`, `PUT /{id}`, `DELETE /{id}` |
| **Standalone Dashboard UI** | `/_/admin` | `GET` (SPA) |

---

## Project Structure

```text
aicb/
├── app/
│   ├── main.py                     # FastAPI application & lifespan
│   ├── admin_ui/                   # Standalone admin dashboard (SPA, served at /_/admin)
│   ├── api/                        # Standalone mode REST API (setup, auth, users, agents, access groups, settings)
│   ├── core/                       # Config, database, security (webhook verifiers, dashboard/JWT/platform-key auth), access-tag resolver
│   ├── channels/                   # WhatsApp, Telegram, Slack, Website Widget endpoints
│   ├── commerce/                   # CartManager, Catalog & Payments (Paystack, Flutterwave, Stripe), image storage
│   ├── ai/                         # Multi-LLM providers, prompts, memory, RAG, tool calling
│   ├── flows/                      # Deterministic 0-token fast-path button engine
│   ├── telemetry/                  # Sannex telemetry dispatcher & 30m sync worker
│   └── models/                     # SQLAlchemy models (Customer, Order, CatalogItem — plus BusinessProfile, AdminUser, Agent, AccessGroup for standalone mode)
├── widget/                         # Embeddable website chat widget (Vite, builds to widget.js)
├── ideas/                          # Local planning docs (gitignored — not part of the repo history)
├── doctor.py                       # Pre-flight diagnostic tool
├── Dockerfile                      # Production container image
├── docker-compose.yml              # Local development compose (port 8422)
├── docker-compose.prod.yml         # Coolify production deployment stack
├── requirements.txt
└── .env.example
```

---

## Authentication model

Four distinct, independent auth mechanisms exist — don't confuse them:

| Mechanism | Direction | Used for | Configured via |
| :--- | :--- | :--- | :--- |
| `AICB_API_KEY` | AgentOS → AICB | Dashboard calls into an AgentOS-connected instance (catalog, gateway-info, orders, image upload) | `.env`, matched against AgentOS's `client_bots.api_key` |
| `SANNEX_API_KEY` | AICB → AgentOS | AICB pulling prompt/catalog/knowledge sync from AgentOS | `.env` |
| `aicb_live_...` platform key | External caller → standalone AICB | Standalone-mode API access with no AgentOS present | Generated and rotated from `/_/admin` — never user-typed |
| Admin JWT session | Browser → standalone AICB | `/_/admin` dashboard login sessions | Signed with `APP_SECRET`, issued by `/api/v1/auth/login` |

Webhook signature verifiers (`verify_whatsapp_signature`, `verify_telegram_secret`, `verify_paystack_signature`, etc.) are a separate, fourth category — they authenticate inbound calls from Meta/Telegram/payment providers, not dashboard/API callers, and pass open (accept everything) when their corresponding secret is left unconfigured in development.
