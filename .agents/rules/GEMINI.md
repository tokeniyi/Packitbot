---
trigger: always_on
---

# Repository Rules
-All development must be done inside the virtual environment.
- Stack: Python / Aiogram 3.x / FastAPI / SQLAlchemy / PostgreSQL / Redis
- Architecture: Domain-driven separation (`service.py`, `repository.py`, `schemas.py`, `state_machine.py`, `business_rules.py`, `events.py`)
- Exceptions: Inherit from custom base domain exception `PackitbotError`. Catch DB `IntegrityError` explicitly.
- Navigation/UX: Every screen must have `🏠 Home` or `⬅ Back` inline buttons. Minimise typing in favor of buttons.