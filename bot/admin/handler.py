# bot/admin/handler.py

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.core.constants.enums import UserRole
from bot.core.constants.messages import MSG_MANAGEMENT_PORTAL
from bot.core.models.user import User

logger = logging.getLogger(__name__)
admin_router = Router()


@admin_router.message(Command("admin"))
async def cmd_admin_portal(
    message: Message,
    state: FSMContext,
    user: User | None = None,  # Injected via AuthMiddleware
) -> None:
    """Renders the Admin Management Portal (Admin-only)."""
    # 1. Clear any active state
    await state.clear()

    # 2. Guard Check: Ensure the user exists and is an ADMIN
    if not user or user.role != UserRole.ADMIN:
        await message.answer("⛔ Access Denied. This command is restricted to administrators.")
        return

    # 3. Send the Admin Management Portal message
    await message.answer(
        MSG_MANAGEMENT_PORTAL,
        parse_mode="Markdown",
        # reply_markup=admin_management_keyboard(), # Optional: attach inline admin buttons
    )