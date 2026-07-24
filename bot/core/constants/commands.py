"""
bot/core/constants/commands.py
Centralized repository for all bot command strings and descriptions.
"""

from aiogram.types import BotCommand

# Command String Constants (without leading slashes for aiogram Command filters)
CMD_START = "start"
CMD_HOME = "home"
CMD_HELP = "help"
CMD_CANCEL = "cancel"
CMD_MENU = "menu"
CMD_ABOUT = "about"

# Student Constants
CMD_NEW_REQUEST = "request"
CMD_MY_REQUESTS = "my_requests"


# Driver Constants
CMD_AVAILABLE_JOBS = "jobs"
CMD_ACTIVE_JOB = "active"
CMD_TOGGLE_DUTY = "duty"

# Admin Commands
CMD_ADMIN = "admin"
CMD_STATS = "stats"
CMD_VERIFY = "verify"
CMD_USERS = "users"
CMD_ORDERS = "orders"
CMD_BROADCAST = "broadcast"


# Telegram Bot Menu Command Definitions
# (Used when calling bot.set_my_commands())

DEFAULT_COMMANDS = [
    BotCommand(command=CMD_START, description="Start the bot"),
    BotCommand(command=CMD_HOME, description="Return to main menu"),
    BotCommand(command=CMD_ABOUT, description="About the bot & services"),  # 👈 Added here
    BotCommand(command=CMD_HELP, description="Get help & support"),
    BotCommand(command=CMD_MENU, description="View available commands"),
    BotCommand(command=CMD_CANCEL, description="Cancel active action"),
]

# 2. STUDENT COMMANDS
STUDENT_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand(command=CMD_HOME, description="Return to main menu"),
    BotCommand(command=CMD_NEW_REQUEST, description="Create new delivery request"),
    BotCommand(command=CMD_MY_REQUESTS, description="View my delivery history"),
    BotCommand(command=CMD_ABOUT, description="About the bot & services"),
    BotCommand(command=CMD_HELP, description="Get help & support"),
    BotCommand(command=CMD_CANCEL, description="Cancel active action"),
]

# 3. DRIVER COMMANDS
DRIVER_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand(command=CMD_HOME, description="Return to main menu"),
    BotCommand(command=CMD_AVAILABLE_JOBS, description="View available orders"),
    BotCommand(command=CMD_ACTIVE_JOB, description="View current delivery"),
    BotCommand(command=CMD_TOGGLE_DUTY, description="Toggle online status"),
    BotCommand(command=CMD_ABOUT, description="About the bot & services"),
    BotCommand(command=CMD_HELP, description="Get help & support"),
    BotCommand(command=CMD_CANCEL, description="Cancel active action"),
]

# 4. ADMIN COMMANDS
ADMIN_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand(command=CMD_ADMIN, description="Open Admin Portal"),
    BotCommand(command=CMD_STATS, description="View system stats"),
    BotCommand(command=CMD_VERIFY, description="Review driver verification"),
    BotCommand(command=CMD_BROADCAST, description="Send announcement"),
]