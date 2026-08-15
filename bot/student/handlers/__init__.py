"""Modular student handlers package.

Exports the composite student_router which aggregates registration,
requests, profile, and feedback sub-routers.
"""

from aiogram import Router

from bot.student.handlers.feedback import feedback_router
from bot.student.handlers.profile import profile_router
from bot.student.handlers.registration import registration_router
from bot.student.handlers.requests import requests_router

student_router = Router()
student_router.include_router(registration_router)
student_router.include_router(requests_router)
student_router.include_router(profile_router)
student_router.include_router(feedback_router)

__all__ = [
    "student_router",
    "registration_router",
    "requests_router",
    "profile_router",
    "feedback_router",
]
