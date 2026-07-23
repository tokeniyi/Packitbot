# Packitbot

Delivery logistics bot for Covenant University residents.

## Prerequisites

- Python 3.12
- PostgreSQL 16
- Redis 7

## Setup

```bash
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `BOT_TOKEN` (from @BotFather) and other configuration values.

## Run dependencies (Docker)

```bash
docker-compose up -d postgres redis
```

## Run the bot (development — polling)

```bash
python -m bot.main
```

## Run tests

```bash
pytest
```

## Project structure

Feature-module layout per `PACKITBOT_ARCHITECTURE_v2.md`:

```
packitbot/
├── bot/
│   ├── core/        # Shared infrastructure, models, middleware, validators
│   ├── student/     # Student-facing feature module
│   ├── driver/      # Driver-facing feature module
│   ├── request/     # DeliveryRequest domain module
│   ├── admin/       # Admin-facing feature module
│   └── common/      # Shared entry points (/start, /help, fallback)
├── alembic/         # Database migrations
└── tests/           # Mirrors feature-module layout
```
