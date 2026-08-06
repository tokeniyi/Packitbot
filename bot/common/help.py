"""Help and about command handlers for the Packitbot Telegram bot.

This module contains handlers for the /help and /about
commands, sending static help and about messages to users.

Function Calls:
    - cmd_help(message) -> None
    - cmd_about(message) -> None

Cross-References:
    - Depends on: aiogram Router, bot.core.constants.messages
    - Imported by: bot/main.py (via help_router)
"""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.core.constants.messages import MSG_ABOUT, MSG_HELP

logger = logging.getLogger(__name__)
help_router = Router()


@help_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle the /help command by sending the help text.

    Args:
        message: The incoming Message object.
    """
    await message.answer(MSG_HELP)


@help_router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    """Handle the /about command by sending the about text.

    Args:
        message: The incoming Message object.
    """
    await message.answer(MSG_ABOUT)