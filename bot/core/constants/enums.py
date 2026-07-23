from enum import Enum


class UserRole(str, Enum):
    STUDENT = "student"
    DRIVER = "driver"
    ADMIN = "admin"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    BANNED = "banned"


class DriverStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class DriverAvailability(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class LuggageSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class RequestStatus(str, Enum):
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
    STUDENT = "student"
    ADMIN = "admin"
    SYSTEM = "system"


class AdminActionType(str, Enum):
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
