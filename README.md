# Packitbot 📦🚀

[![GitHub Release](https://img.shields.io/github/v/release/tokeniyi/Packitbot?color=blue&label=version)](https://github.com/tokeniyi/Packitbot/releases)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/aiogram-3.x-blueviolet.svg)](https://docs.aiogram.dev/)
[![Database](https://img.shields.io/badge/PostgreSQL-16-sky.svg)](https://www.postgresql.org/)
[![Cache](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A modern, domain-driven Telegram bot for managing student package requests and driver delivery logistics within Covenant University campus.

---

## 📌 Overview

**Packitbot** solves on-campus delivery challenges by connecting Covenant University residents (students) with verified campus drivers. It automates the end-to-end lifecycle of package delivery requests—from creation, matching, and pickup verification to delivery confirmation and administrative oversight.

### Key Features

- 👤 **Role-Based Workflows (Student, Driver, Admin):** Dynamic Telegram bot menus and command scopes tailored to each authenticated role.
- 📦 **Student Request Management:** Multi-step Finite State Machine (FSM) forms for scheduling delivery requests with lead-time validation, tracking order history, and cancellation support.
- 🚗 **Driver Logistics & Duty Control:** Driver registration, duty toggle (online/offline), job discovery, order claiming, state transitions (pickup, transit, delivered), and earnings tracking.
- 🔒 **Admin Portal & Driver Verification:** System statistics, driver verification review queue, broadcast notifications, user lookup, and manual order overrides.
- ⚡ **Domain-Driven Architecture:** Clean separation of concerns with domain state machines, repositories, business rules, schemas, and events.
- 🔄 **Production Infrastructure:** Asynchronous DB access (SQLAlchemy 2.0 + asyncpg), Redis-backed FSM storage & rate limiting, Alembic database migrations, and Docker containerization.

---

## 🏗️ Architecture & Tech Stack

### Technology Stack
- **Language:** Python 3.12
- **Telegram Bot Framework:** [Aiogram 3.x](https://docs.aiogram.dev/)
- **Database Engine:** PostgreSQL 16 (via SQLAlchemy 2.0 Async & `asyncpg`)
- **FSM & Caching:** Redis 7 (`redis-py` async)
- **Migrations:** Alembic
- **Testing:** Pytest & `pytest-asyncio`
- **Containerization:** Docker & Docker Compose

### Project Structure

```
packitbot/
├── alembic/                # Alembic database migration scripts & environment
├── bot/
│   ├── main.py             # Application entry point, DB initialization & bot startup
│   ├── admin/              # Admin feature module (handlers, keyboards, services, FSM states)
│   ├── common/             # Shared handlers (/start, /help, /about, fallbacks)
│   ├── core/               # Shared infrastructure & core services
│   │   ├── config.py       # Pydantic Settings configuration
│   │   ├── constants/      # Enums, commands, system messages
│   │   ├── db/             # Async DB session factory & base models
│   │   ├── middlewares/    # Auth, DB Session, Logging, and Throttling middlewares
│   │   ├── models/         # SQLAlchemy ORM models (User, DeliveryRequest, AdminProfile, etc.)
│   │   └── repositories/   # Base database repositories
│   ├── driver/             # Driver feature module (jobs, duty toggle, active deliveries)
│   ├── request/            # DeliveryRequest domain module (FSM state machine, rules, events)
│   └── student/            # Student feature module (request creation, profile, order history)
├── tests/                  # Pytest suite (unit, integration, and fixtures)
├── Dockerfile              # Production Dockerfile
├── docker-compose.yml      # Service orchestration (PostgreSQL, Redis, Bot)
├── requirements.txt        # Python dependency manifest
└── pyproject.toml          # Project configuration & pytest options
```

---

## 📋 Prerequisites

Ensure you have the following installed on your machine before setup:

- **Python:** `^3.12`
- **PostgreSQL:** `^16`
- **Redis:** `^7`
- **Docker & Docker Compose** (Optional, recommended for running dependencies)
- **Telegram Bot Token:** Obtained from [@BotFather](https://t.me/BotFather)

---

## 🚀 Getting Started & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/tokeniyi/packitbot.git
cd packitbot
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update your variables:

```bash
cp .env.example .env
```

#### Environment Variables Reference

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot API token from BotFather | `123456789:ABCdefGHI...` |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://packitbot:packitbot@localhost:5433/packitbot` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `SEED_ADMIN_TELEGRAM_IDS` | Comma-separated Telegram User IDs for initial admin seeding | `123456789,987654321` |
| `MAX_REQUEST_LEAD_DAYS` | Maximum lead days in advance for scheduling requests | `7` |
| `DEFAULT_THROTTLE_RATE` | Throttle rate limit (requests per second) | `1.0` |
| `LOG_LEVEL` | Application logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `WEBHOOK_URL` | Public HTTPS URL for Telegram webhooks (leave empty for polling mode) | `""` |

---

### 5. Run Database & Redis Dependencies

Using Docker Compose:

```bash
docker-compose up -d postgres redis
```

### 6. Run Database Migrations

Apply database schema migrations using Alembic:

```bash
alembic upgrade head
```

---

## 💻 Running the Application

### Development Mode (Polling)

To run the bot locally in long-polling mode:

```bash
python -m bot.main
```

### Production Mode (Docker Compose)

To build and launch the entire stack (Postgres, Redis, and Bot):

```bash
docker-compose up --build -d
```

---

## 🎮 Usage & Commands

### General Commands
- `/start` - Start interacting with Packitbot
- `/home` - Return to the role-specific main menu
- `/about` - Information about Packitbot services
- `/help` - Get support and user guidance
- `/menu` - View available actions
- `/cancel` - Cancel active FSM form/action

### Student Commands
- `/request` - Create a new package delivery request
- `/my_requests` - View active and past delivery history
- `/profile` - Manage student profile details

### Driver Commands
- `/duty` - Toggle online/offline status
- `/jobs` - Browse available package delivery jobs
- `/active` - View currently accepted delivery details

### Admin Commands
- `/admin` - Access Admin Control Panel
- `/stats` - View system-wide metrics and orders report
- `/verify` - Review pending driver registration applications
- `/users` - Search or filter registered students & drivers
- `/orders` - View active, pending, or completed deliveries
- `/broadcast` - Send system announcements to users

---

## 🧪 Testing & Linting

Unit and integration tests are located under the `tests/` directory.

### Run Test Suite

```bash
pytest
```

---

## 🤝 Contributing & License

Contributions are welcome! Please ensure all PRs follow the domain-driven architecture guidelines, pass test suites, and include clear inline documentation.

### License

This project is licensed under the [MIT License](LICENSE).
