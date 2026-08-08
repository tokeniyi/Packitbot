"""Centralized repository for all bot command strings and descriptions.

This module defines command string constants (without leading
slashes for aiogram Command filters) and the BotCommand
objects used when registering command menus with Telegram.

Constants:
    - CMD_START, CMD_HOME, CMD_HELP, CMD_CANCEL, CMD_MENU, CMD_ABOUT
    - CMD_NEW_REQUEST, CMD_MY_REQUESTS, CMD_PROFILE (Student)
    - CMD_AVAILABLE_JOBS, CMD_ACTIVE_JOB, CMD_TOGGLE_DUTY (Driver)
    - CMD_ADMIN, CMD_STATS, CMD_VERIFY, CMD_USERS, CMD_ORDERS, CMD_BROADCAST (Admin)
    - DEFAULT_COMMANDS, STUDENT_COMMANDS, DRIVER_COMMANDS, ADMIN_COMMANDS
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
CMD_PROFILE = "profile"


# Driver Constants
CMD_AVAILABLE_JOBS = "jobs"
CMD_ACTIVE_JOB = "active"
CMD_TOGGLE_DUTY = "duty"

# Admin Commands
CMD_ADMIN = "admin"
CMD_DRIVERS = "drivers"
CMD_STATS = "stats"
CMD_VERIFY = "verify"
CMD_USERS = "users"
CMD_ORDERS = "orders"
CMD_BROADCAST = "broadcast"
CMD_ASSIGN = "assign"

# Admin Drivers
CMD_ADD_DRIVER = "add_driver"


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
    BotCommand(command=CMD_PROFILE, description="View Profile"),
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
    BotCommand(command=CMD_USERS, description="Search or view registered students and drivers"),
    BotCommand(command=CMD_ORDERS, description=" View active, pending, or completed deliveries"),
    BotCommand(command=CMD_DRIVERS, description="  lists all driver record"),
    BotCommand(command=CMD_ASSIGN, description="  assign request to a driver"),
    BotCommand(command=CMD_ADD_DRIVER, description="Add authorized driver"),
]