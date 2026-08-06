"""Enumeration types used throughout the Packitbot application.

This module defines all aiogram-compatible StrEnum classes
for user roles, account statuses, driver statuses, request
statuses, cancellation actors, admin action types, and
notification types.

Enums:
    - UserRole: The role assigned to a user (student, driver, admin).
    - AccountStatus: Whether a user account is active or banned.
    - DriverStatus: The approval status of a driver application.
    - DriverAvailability: The current availability of a driver.
    - VerificationStatus: Whether a student profile is verified.
    - LuggageSize: The size category of a luggage item.
    - RequestStatus: The lifecycle status of a delivery request.
    - CancelledBy: Who initiated the cancellation of a request.
    - AdminActionType: The type of action performed by an admin.
    - NotificationType: The type of notification event.
"""

from enum import Enum


class UserRole(str, Enum):
    """The role assigned to a user in the system."""
    STUDENT = "student"
    DRIVER = "driver"
    ADMIN = "admin"


class AccountStatus(str, Enum):
    """The current status of a user account."""
    ACTIVE = "active"
    BANNED = "banned"


class DriverStatus(str, Enum):
    """The approval status of a driver application."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class DriverAvailability(str, Enum):
    """The current availability state of a driver."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class VerificationStatus(str, Enum):
    """The verification state of a student profile."""
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class LuggageSize(str, Enum):
    """The size category of a luggage item."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class RequestStatus(str, Enum):
    """The lifecycle status of a delivery request."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    REJECTED_BY_DRIVER = "rejected_by_driver"
    EN_ROUTE_TO_PICKUP = "en_route_to_pickup"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CancelledBy(str, Enum):
    """Indicates who initiated the cancellation of a request."""
    STUDENT = "student"
    ADMIN = "admin"
    SYSTEM = "system"


class AdminActionType(str, Enum):
    """The type of action performed by an administrator."""
    APPROVE_DRIVER = "approve_driver"
    REJECT_DRIVER = "reject_driver"
    SUSPEND_DRIVER = "suspend_driver"
    BAN_USER = "ban_user"
    UNBAN_USER = "unban_user"
    ASSIGN_REQUEST = "assign_request"
    CANCEL_REQUEST = "cancel_request"
    PROMOTE_ADMIN = "promote_admin"
    BROADCAST = "broadcast"


class NotificationType(str, Enum):
    """The type of notification event triggered in the system."""
    REQUEST_SUBMITTED = "request_submitted"
    REQUEST_ASSIGNED = "request_assigned"
    REQUEST_ACCEPTED = "request_accepted"
    REQUEST_REJECTED_BY_DRIVER = "request_rejected_by_driver"
    STATUS_UPDATED = "status_updated"
    REQUEST_CANCELLED = "request_cancelled"
    DRIVER_APPROVED = "driver_approved"
    DRIVER_REJECTED = "driver_rejected"
    DELIVERY_COMPLETED = "delivery_completed"
    BROADCAST = "broadcast"
