---
trigger: always_on
---

# Repository Rules
- Stack: Python / Aiogram 3.x / FastAPI / SQLAlchemy / PostgreSQL / Redis
- Architecture: Domain-driven separation (`service.py`, `repository.py`, `schemas.py`, `state_machine.py`, `business_rules.py`, `events.py`)
- Exceptions: Inherit from custom base domain exception `PackitbotError`. Catch DB `IntegrityError` explicitly.
- Navigation/UX: Every screen must have `🏠 Home` or `⬅ Back` inline buttons. Minimise typing in favor of buttons.
