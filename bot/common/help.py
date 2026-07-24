import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.core.constants.messages import MSG_ABOUT, MSG_HELP

logger = logging.getLogger(__name__)
help_router = Router()


@help_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(MSG_HELP)


@help_router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer(MSG_ABOUT)