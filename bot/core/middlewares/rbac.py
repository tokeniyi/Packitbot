"""RBAC middleware for role-based command access control.

This middleware runs in the aiogram update pipeline **after**
``AuthMiddleware`` (which injects ``data["user"]``) and ``DbSessionMiddleware``
(which injects ``data["session"]``).  It enforces two orthogonal layers of
access control:

1. **Registration gate** — users without a fully-completed profile for their
   current role are blocked from issuing role-specific commands.
2. **Role gate** — even registered users may only invoke commands that are
   mapped to their role.

A small set of *public* commands (``start``, ``help``, ``about``, ``cancel``,
``menu``, ``home``) are always allowed so that every user — including
unregistered ones — can navigate the bot.

Special case: the ``/register_driver`` command is gated by a pre-authorization
list (``AuthorizedDriver``).  A pre-authorized user — regardless of whether
they have the ``DRIVER`` role yet — may start the registration flow if their
Telegram ID appears on the pre-approved list.

Commands that are not recognized as public or role-specific are rejected with
an "unknown command" message so users get clear feedback.
"""

import logging
from typing import Any, Callable

from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from sqlalchemy import select

from bot.core.constants.enums import UserRole
from bot.core.constants.messages import (
    MSG_ACCESS_DENIED_NOT_FULLY_REGISTERED,
    MSG_ACCESS_DENIED_ROLE,
    MSG_ACCESS_DENIED_UNREGISTERED,
    MSG_DRIVER_NOT_AUTHORIZED,
    MSG_UNKNOWN_COMMAND,
)
from bot.core.keyboards.common_kb import HomeButton
from bot.core.models.admin_profile import AdminProfile
from bot.core.models.driver_profile import DriverProfile
from bot.core.models.student_profile import StudentProfile

logger = logging.getLogger(__name__)


class RBACMiddleware(BaseMiddleware):
    """Role-based access control for bot commands.

    Inspects each incoming ``Update`` for a leading slash-command, then
    decides whether the authenticated user may proceed based on their
    role and registration completeness.

    Public commands always pass through.  Role-specific commands require
    that the user has a non-null ``role`` and a matching profile record.
    The ``/register_driver`` command additionally requires the user to be
    present on the pre-authorized driver list.

    Attributes:
        home: A ``HomeButton`` markup attached to denial replies.
    """

    PUBLIC_COMMANDS = {"start", "help", "about", "cancel", "menu", "home"}

    ROLE_COMMANDS = {
        UserRole.STUDENT: {"request", "my_requests", "profile"},
        UserRole.DRIVER: {"register_driver", "active_delivery", "toggle_availability", "cancel_driver_reg"},
        UserRole.ADMIN: {"admin", "stats", "verify", "users", "orders", "drivers", "assign", "broadcast", "add_driver"},
    }

    def __init__(self) -> None:
        """Initialize the middleware with a reusable Home button markup."""
        self.home = HomeButton()

    def _extract_command(self, event: types.Update) -> str:
        """Extract the command name (without slash) from a message.

        Handles ``/command@botname`` and ``/command <args>`` by splitting
        on whitespace and the ``@`` separator.  Returns an empty string
        for non-command messages or callback queries.

        Args:
            event: The incoming aiogram ``Update``.

        Returns:
            The bare command name (e.g. ``start``), or ``""`` when the
            event is not a slash-command message.
        """
        if event.message and event.message.text:
            text = event.message.text.strip()
            if text.startswith("/"):
                return text.split()[0].lstrip("/").split("@")[0]
        return ""

    async def _is_fully_registered(self, user: Any, session: Any) -> bool:
        """Check that the user has a role *and* a matching profile record.

        Args:
            user: The ``User`` ORM instance injected by ``AuthMiddleware``.
            session: The ``AsyncSession`` injected by ``DbSessionMiddleware``.

        Returns:
            ``True`` when both the role is set and a corresponding profile
            row exists for the user; ``False`` otherwise.
        """
        if user.role is None:
            return False

        if user.role == UserRole.STUDENT:
            stmt = select(StudentProfile).where(StudentProfile.user_id == user.id)
        elif user.role == UserRole.DRIVER:
            stmt = select(DriverProfile).where(DriverProfile.user_id == user.id)
        elif user.role == UserRole.ADMIN:
            stmt = select(AdminProfile).where(AdminProfile.user_id == user.id)
        else:
            return False

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _reply_denied(self, event: types.Update, message_text: str) -> None:
        """Send a denial message appropriate to the update type.

        For messages, an inline reply with a Home button is sent.  For
        callback queries, an alert dialog is shown.

        Args:
            event: The incoming aiogram ``Update``.
            message_text: The denial message to send.
        """
        if event.message:
            await event.message.answer(message_text, reply_markup=self.home)
        elif event.callback_query:
            await event.callback_query.answer(message_text, show_alert=True)

    async def __call__(
        self,
        handler: Callable[[types.Update, dict[str, Any]], Any],
        event: types.Update,
        data: dict[str, Any],
    ) -> Any:
        """Enforce role-based command access before invoking the handler.

        Args:
            handler: The next handler (or downstream middleware) in the chain.
            event: The incoming aiogram ``Update``.
            data: The handler data dict containing ``user`` and ``session``.

        Returns:
            The result of the downstream handler, or ``None`` if the
            command was blocked by an access-control rule.
        """
        user = data.get("user")
        if not user:
            return await handler(event, data)

        command = self._extract_command(event)

        # Public commands always allowed
        if command in self.PUBLIC_COMMANDS:
            return await handler(event, data)

        session = data.get("session")

        if command:
            # Special: driver registration bypass for pre-authorized users.
            # A user does not need the DRIVER role yet â being on the
            # pre-authorized list is sufficient to start the registration flow.
            if command == "register_driver":
                from bot.driver.service import is_authorized_driver

                if await is_authorized_driver(user.telegram_id, session):
                    return await handler(event, data)
                if user.role == UserRole.DRIVER:
                    await self._reply_denied(event, MSG_DRIVER_NOT_AUTHORIZED)
                    return

            # Reject unknown commands â commands that are not in any role's
            # allowed set and not in PUBLIC_COMMANDS.
            all_known = self.PUBLIC_COMMANDS | set().union(*self.ROLE_COMMANDS.values())
            if command not in all_known:
                await self._reply_denied(event, MSG_UNKNOWN_COMMAND)
                return

            # Unregistered users (role is None) blocked from role-specific
            # slash-commands.  Callbacks and non-command text are allowed
            # through so that role-selection flows (e.g. the start-menu
            # "student"/"driver" buttons) and other UI interactions work.
            if user.role is None:
                await self._reply_denied(event, MSG_ACCESS_DENIED_UNREGISTERED)
                return

            is_registered = await self._is_fully_registered(user, session)

            # Block fully-unregistered users from role commands
            if not is_registered:
                await self._reply_denied(event, MSG_ACCESS_DENIED_NOT_FULLY_REGISTERED)
                return

            # Check role alignment
            allowed = self.ROLE_COMMANDS.get(user.role, set())
            if command not in allowed:
                await self._reply_denied(event, MSG_ACCESS_DENIED_ROLE)
                return

        return await handler(event, data)
