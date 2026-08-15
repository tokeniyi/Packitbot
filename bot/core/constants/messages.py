"""User-facing message strings, system alerts, and logging templates for Packitbot.

This module centralizes all textual responses, alerts, logs, and notification templates
grouped by functional category while maintaining 100% backward compatibility with legacy constants.
"""

from typing import Final

# ==============================================================================
# 1. COMMAND & NAVIGATION RESPONSES
# ==============================================================================
class CommandResponses:
    START_ROLE_SELECTION: Final[str] = "Welcome to Packitbot! Are you a Student or a Driver?"
    START_ROLE_SELECTION_STUDENT: Final[str] = "📚 Student"
    START_ROLE_SELECTION_DRIVER: Final[str] = "🚗 Driver"
    WELCOME_GENERAL: Final[str] = (
        "👋 Welcome to **Packitbot**!\n\n"
        "The easiest way to send and receive packages on Covenant University campus.\n\n"
        "🎓 **Students:** Send items to friends or family on campus.\n"
        "🚗 **Drivers:** Earn money by delivering packages.\n"
        "⚙️ **Admins:** Keep the system running smoothly.\n\n"
        "Ready to get started?"
    )
    START_ADMIN_WELCOME: Final[str] = (
        "⚙️ **Admin Portal Active**\n\n"
        "Welcome back, Boss! You have full administrative access.\n\n"
        "🛠️ **Quick Actions:**\n"
        "• View active dispatch orders\n"
        "• Manage verified drivers & students\n"
        "• System metrics & logs\n\n"
        "Type /admin to open the management panel."
    )
    MANAGEMENT_PORTAL: Final[str] = (
        "⚙️ **Admin Management Panel**\n\n"
        "Welcome, Admin! Here are the commands and controls available to you:\n\n"
        "📊 **System & Metrics**\n"
        "• /admin — Re-open this management portal\n"
        "• /stats — View live delivery metrics & system stats\n\n"
        "👥 **User & Verification Management**\n"
        "• /verify — Review & verify pending driver accounts\n"
        "• /users — Search or view registered students and drivers\n"
        "• /drivers — View and manage all driver records\n\n"
        "📦 **Logistics & Orders**\n"
        "• /orders — View active, pending, or completed deliveries\n"
        "• /broadcast — Send an announcement message to all users\n\n"
        "💡 *Tip: You can also use the inline buttons below to navigate quick actions!(not implemented yet 😁*"
    )
    STATS: Final[str] = (
        "📊 **System Statistics**\n\n"
        "📦 **Delivery Metrics**\n"
        "• Total Requests: `{total_requests}`\n"
        "• Pending: `{pending_requests}`\n"
        "• Assigned: `{assigned_requests}`\n"
        "• Accepted: `{accepted_requests}`\n"
        "• En Route: `{en_route_requests}`\n"
        "• Picked Up: `{picked_up_requests}`\n"
        "• In Transit: `{in_transit_requests}`\n"
        "• Delivered: `{delivered_requests}`\n"
        "• Cancelled: `{cancelled_requests}`\n"
        "• Failed: `{failed_requests}`\n"
        "• Rejected by Driver: `{rejected_by_driver_requests}`\n"
        "• Avg Delivery Time: `{avg_delivery_duration}`\n\n"
        "👥 **User Overview**\n"
        "• Total Users: `{total_users}`\n"
        "• Students: `{total_students}`\n"
        "• Drivers: `{total_drivers}`\n"
        "• Admins: `{total_admins}`\n\n"
        "🚗 **Driver Status**\n"
        "• Approved: `{approved_drivers}`\n"
        "• Active (Online/Busy): `{active_drivers}`\n"
        "• Pending Approval: `{pending_drivers}`\n"
        "• Rejected: `{rejected_drivers}`\n"
        "• Suspended: `{suspended_drivers}`\n\n"
        "⭐ **Feedback**\n"
        "• Total Ratings: `{total_feedbacks}`\n"
        "• Avg Rating: `{avg_rating}`\n"
    )
    STUDENT_WELCOME: Final[str] = (
        "🎓 **Welcome to the Student Portal!**\n\n"
        "We're ready whenever you are! 📦\n\n"
        "🚀 **Get Started**\n"
        "• /request — Create a new delivery request\n"
        "• /my_requests — View and track your requests\n\n"
        "👤 **Your Profile:**\n"
        "• View your details, default hall, and track your active or past delivery requests anytime.\n"
        "• Access it directly via the **Profile** button on your main menu or send /profile!\n\n"
        "⚙️ Want to update your profile? Send /profile to open your profile!"
    )
    DRIVER_WELCOME: Final[str] = "🚗 **Driver Portal**\n\nReady to earn by delivering? Let's get you set up!"
    ABOUT: Final[str] = (
        "🚀 **Packitbot** — CU delivery logistics, simplified.\n\n"
        "🎓 **Students** request deliveries.\n"
        "🚗 **Drivers** accept & complete them.\n"
        "⚙️ **Admins** keep everything running smoothly!\n\n"
        "👋 New here or ran into an issue? Type /help for quick support, "
        "or send /menu to explore all the things you can do!"
    )

    @staticmethod
    def get_help_message(support_link: str = "https://t.me/PackitbotSupport") -> str:
        return (
            "👋 **Need help getting started?**\n\n"
            "📦 **Packitbot** connects Covenant University students with trusted drivers "
            "for fast, reliable campus deliveries.\n\n"
            "💡 **Quick Tips:**\n"
            "• Use the menu buttons below to navigate.\n"
            "• Type /start or /home anytime to return to the main menu.\n"
            "• Want to reset or start over? Just send /cancel!\n\n"
            f"💬 **Having any issues?** [Contact Support Directly]({support_link})"
        )


# ==============================================================================
# 2. ERROR & RBAC MESSAGES
# ==============================================================================
class ErrorMessages:
    SOMETHING_WENT_WRONG: Final[str] = "❌ Something went wrong. Please try again."
    SESSION_UNAVAILABLE: Final[str] = "⚠️ Session unavailable. Please try again."
    NO_PERMISSION: Final[str] = "⛔ You don't have permission to perform this action."
    ADMIN_ACCESS_REQUIRED: Final[str] = "⛔ Admin access required."
    INVALID_INPUT: Final[str] = "🤔 That input doesn't look right. Please try again."
    SLOW_DOWN: Final[str] = "⏳ **Slow down!** You're tapping buttons too fast."
    BANNED: Final[str] = "🔒 **Account Restricted.** Your account has been restricted. Contact an admin for assistance."
    UNKNOWN_COMMAND: Final[str] = "❓ Unknown command. Use /help to see available commands."
    USER_NOT_FOUND: Final[str] = "⚠️ User profile not found."
    INVALID_REQUEST_ID: Final[str] = "⚠️ Invalid request ID."
    REQUEST_NOT_FOUND: Final[str] = "⚠️ Request not found or permission denied."
    REQUEST_EDIT_NOT_ALLOWED: Final[str] = "⚠️ Only requests in PENDING status can be edited."
    REQUEST_CANCEL_NOT_ALLOWED: Final[str] = "⚠️ Request cannot be cancelled in its current status."
    DRIVER_NOT_APPROVED: Final[str] = (
        "🚗 **Driver Access Restricted**\n\n"
        "Only approved drivers can select this role.\n"
        "Please contact an admin to request driver approval!"
    )
    DRIVER_INVITATION_ONLY: Final[str] = (
        "⛔ Driver registration is currently by invitation only.\n\n"
        "An admin needs to add your Telegram ID to the authorized driver list first.\n"
        "Please contact an admin to request driver access."
    )
    DRIVER_PENDING_APPROVAL: Final[str] = (
        "⏳ Your driver registration is currently <b>PENDING APPROVAL</b>.\n"
        "Please wait for an administrator to review your application."
    )
    ACCESS_DENIED_ROLE: Final[str] = "⛔ Access denied. You do not have permission to use this command."
    ACCESS_DENIED_UNREGISTERED: Final[str] = "⛔ Your registration is not complete. Use /start to begin setup."
    ACCESS_DENIED_NOT_FULLY_REGISTERED: Final[str] = "⛔ Your registration is not fully completed. Please complete registration first."
    DRIVER_NOT_AUTHORIZED: Final[str] = "⛔ Driver registration requires pre-authorization. Please contact an admin to request driver access."


# ==============================================================================
# 3. SUCCESS & CONFIRMATION MESSAGES
# ==============================================================================
class SuccessMessages:
    ACTION_CONFIRMED: Final[str] = "✅ Done!"
    ACTION_CANCELLED: Final[str] = "🛑 Action cancelled."
    NO_CHANGES_TO_SAVE: Final[str] = "ℹ️ No changes to save."
    REGISTRATION_COMPLETE: Final[str] = "🎉 **Registration complete!** You can now create delivery requests."
    DRIVER_ALREADY_APPROVED: Final[str] = "✅ You are already registered and approved as a driver!"
    DRIVER_SUBMISSION_SUCCESS: Final[str] = "⏳ **Application submitted!** An admin will review your profile shortly."
    DRIVER_EDIT_SUCCESS: Final[str] = "✅ **Driver record updated successfully!**\n\nField: `{field}`\nNew value: `{value}`"
    DRIVER_REMOVED: Final[str] = "🗑️ **Driver record removed successfully.**\n\nDriver **{full_name}** has been removed from the system."
    BROADCAST_SENT: Final[str] = "📢 **Broadcast sent successfully** to {count} users."
    REQUEST_CREATED: Final[str] = "🚀 **Request submitted!** We'll notify you as soon as a driver accepts."


# ==============================================================================
# 4. REGISTRATION & FORM PROMPTS
# ==============================================================================
class RegistrationMessages:
    STEP_PROMPT: Final[str] = "📌 **Step {current} of {total}** {progress_bar}\n\n{prompt}"
    STUDENT_ENTER_FULL_NAME: Final[str] = "👤 **What's your full name?**\n*(e.g., John Doe)*"
    STUDENT_ENTER_MATRIC: Final[str] = "🪪 **Enter your matriculation number.**\n*(e.g., 21AB1234)*"
    STUDENT_ENTER_HALL: Final[str] = "🏛️ **Which hall of residence do you live in?**"
    STUDENT_ENTER_PHONE: Final[str] = "📱 **Share your phone number so drivers can reach you.**"
    STUDENT_REVIEW_TITLE: Final[str] = "📋 **Let's confirm your details:**"
    DRIVER_ENTER_FULL_NAME: Final[str] = "👤 **What's your full name?**"
    DRIVER_ENTER_PHONE: Final[str] = "📱 **Share your phone number.**"
    DRIVER_CHOOSE_VEHICLE: Final[str] = "🚘 **What type of vehicle do you drive?**"
    DRIVER_ENTER_PLATE: Final[str] = "🔤 **Enter your vehicle plate number.**"
    DRIVER_ENTER_LICENSE: Final[str] = "🪪 **Enter your driver's license number.**"
    DRIVER_REVIEW_TITLE: Final[str] = "📋 **Confirm your driver details:**"
    INVALID_FULL_NAME: Final[str] = "⚠️ Please enter your full name (first and last name)."
    INVALID_MATRIC: Final[str] = "⚠️ That doesn't look like a valid matric number. Please try again."
    INVALID_PHONE: Final[str] = "⚠️ Please enter a valid 11-digit Nigerian phone number."
    INVALID_PLATE: Final[str] = "⚠️ Please enter a valid plate number."
    INVALID_LICENSE: Final[str] = "⚠️ Please enter a valid license number."
    INVALID_VEHICLE: Final[str] = "⚠️ Please select a vehicle type from the buttons."


# ==============================================================================
# 5. REQUEST & DISPATCH MESSAGES
# ==============================================================================
class RequestMessages:
    CONFIRM_HALL: Final[str] = "📍 **Pickup Location:** {hall}\nDo you want to use this location?"
    ENTER_PICKUP_DETAIL: Final[str] = "📍 **Where should the driver meet you?**\n*(e.g., Hostel Block B, Room 12)*"
    ENTER_PICKUP_DETAIL_PROMPT: Final[str] = ENTER_PICKUP_DETAIL
    ENTER_DROPOFF_ADDRESS: Final[str] = "🎯 **Where should the driver deliver this package?**"
    ENTER_DROPOFF_LANDMARK: Final[str] = "🗺️ **Any nearby landmark?** *(optional, send 'Skip' if none)*"
    ENTER_RECIPIENT_NAME: Final[str] = "👤 **Who is receiving this package?**"
    ENTER_RECIPIENT_PHONE: Final[str] = "📱 **What's the recipient's phone number?**"
    CHOOSE_LUGGAGE_SIZE: Final[str] = "📦 **How big is the item/luggage?**"
    ENTER_LUGGAGE_COUNT: Final[str] = "🔢 **How many items are you sending ({min}-{max})?**"
    ENTER_PREFERRED_DATE: Final[str] = "📅 **When should this be picked up?**"
    CHOOSE_TIME_WINDOW: Final[str] = "⏰ **Pick a preferred time window:**"
    ENTER_SPECIAL_INSTRUCTIONS: Final[str] = "📝 **Any special instructions for the driver?** *(optional)*"
    REVIEW_TITLE: Final[str] = "🧾 **Review your delivery request:**"
    SELECT_HALL: Final[str] = "🏛️ **Which hall of residence do you live in?**"
    EMPTY_STATE_STUDENT: Final[str] = "📭 You haven't created any delivery requests yet.\nTap **📦 New Request** to get started!"
    EMPTY_STATE_DRIVER: Final[str] = "🛋️ You don't have an active delivery right now. We'll notify you when a request comes in!"
    REQUESTS_LIST_TITLE: Final[str] = "📋 <b>Your Delivery Requests:</b>"


# ==============================================================================
# 6. LOGGING TEMPLATES
# ==============================================================================
class LogMessages:
    BOT_STARTED: Final[str] = "Bot startup completed successfully."
    BOT_STOPPED: Final[str] = "Bot shutdown signal received."
    STATS_FETCH_FAILED: Final[str] = "Error fetching system statistics: %s"
    CUSTOM_MENU_FAILED: Final[str] = "Failed to set custom menu for chat_id=%s: %s"
    FALLBACK_TELEGRAM_ERROR: Final[str] = "TelegramBadRequest while sending fallback message: %s"
    STALE_CALLBACK: Final[str] = "Stale or invalid callback query in fallback: %s"
    UNHANDLED_UPDATE: Final[str] = "Unhandled update type in fallback: %s"
    DRIVER_REG_STARTED: Final[str] = "Driver registration initiated for user_id=%s"
    DRIVER_ASSIGNED: Final[str] = "Driver %s assigned to delivery request %s by admin %s"


# ==============================================================================
# 7. BACKWARDS COMPATIBILITY EXPORTS
# ==============================================================================
MSG_START_ROLE_SELECTION = CommandResponses.START_ROLE_SELECTION
MSG_START_ROLE_SELECTION_STUDENT = CommandResponses.START_ROLE_SELECTION_STUDENT
MSG_START_ROLE_SELECTION_DRIVER = CommandResponses.START_ROLE_SELECTION_DRIVER
MSG_START_ADMIN_WELCOME = CommandResponses.START_ADMIN_WELCOME
MSG_MANAGEMENT_PORTAL = CommandResponses.MANAGEMENT_PORTAL
MSG_STATS = CommandResponses.STATS
MSG_STUDENT_WELCOME = CommandResponses.STUDENT_WELCOME
MSG_DRIVER_WELCOME = CommandResponses.DRIVER_WELCOME
MSG_WELCOME_GENERAL = CommandResponses.WELCOME_GENERAL
MSG_ABOUT = CommandResponses.ABOUT
SUPPORT_LINK = "https://t.me/PackitbotSupport"
MSG_HELP = CommandResponses.get_help_message(SUPPORT_LINK)

MSG_SOMETHING_WENT_WRONG = ErrorMessages.SOMETHING_WENT_WRONG
MSG_NO_PERMISSION = ErrorMessages.NO_PERMISSION
MSG_INVALID_INPUT = ErrorMessages.INVALID_INPUT
MSG_SLOW_DOWN = ErrorMessages.SLOW_DOWN
MSG_BANNED = ErrorMessages.BANNED
MSG_DRIVER_NOT_APPROVED = ErrorMessages.DRIVER_NOT_APPROVED
MSG_ACCESS_DENIED_ROLE = ErrorMessages.ACCESS_DENIED_ROLE
MSG_ACCESS_DENIED_UNREGISTERED = ErrorMessages.ACCESS_DENIED_UNREGISTERED
MSG_ACCESS_DENIED_NOT_FULLY_REGISTERED = ErrorMessages.ACCESS_DENIED_NOT_FULLY_REGISTERED
MSG_DRIVER_NOT_AUTHORIZED = ErrorMessages.DRIVER_NOT_AUTHORIZED
MSG_UNKNOWN_COMMAND = ErrorMessages.UNKNOWN_COMMAND

MSG_ACTION_CONFIRMED = SuccessMessages.ACTION_CONFIRMED
MSG_ACTION_CANCELLED = SuccessMessages.ACTION_CANCELLED
MSG_BROADCAST_SENT = SuccessMessages.BROADCAST_SENT
MSG_DRIVER_EDIT_SUCCESS = SuccessMessages.DRIVER_EDIT_SUCCESS
MSG_DRIVER_REMOVED = SuccessMessages.DRIVER_REMOVED

MSG_REG_STEP_PROMPT = RegistrationMessages.STEP_PROMPT
MSG_REG_ENTER_FULL_NAME = RegistrationMessages.STUDENT_ENTER_FULL_NAME
MSG_REG_ENTER_MATRIC = RegistrationMessages.STUDENT_ENTER_MATRIC
MSG_REG_ENTER_HALL = RegistrationMessages.STUDENT_ENTER_HALL
MSG_REG_ENTER_PHONE = RegistrationMessages.STUDENT_ENTER_PHONE
MSG_REG_REVIEW_TITLE = RegistrationMessages.STUDENT_REVIEW_TITLE
MSG_REG_EDIT = "✏️ Edit"
MSG_REG_SUBMIT = "✅ Submit"
MSG_REG_SUCCESS = SuccessMessages.REGISTRATION_COMPLETE
MSG_REG_INVALID_FULL_NAME = RegistrationMessages.INVALID_FULL_NAME
MSG_REG_INVALID_MATRIC = RegistrationMessages.INVALID_MATRIC
MSG_REG_INVALID_PHONE = RegistrationMessages.INVALID_PHONE

MSG_DRIVER_PENDING_APPROVAL = ErrorMessages.DRIVER_PENDING_APPROVAL
MSG_DRIVER_STEP_PROMPT = RegistrationMessages.STEP_PROMPT
MSG_DRIVER_ENTER_FULL_NAME = RegistrationMessages.DRIVER_ENTER_FULL_NAME
MSG_DRIVER_ENTER_PHONE = RegistrationMessages.DRIVER_ENTER_PHONE
MSG_DRIVER_CHOOSE_VEHICLE = RegistrationMessages.DRIVER_CHOOSE_VEHICLE
MSG_DRIVER_ENTER_PLATE = RegistrationMessages.DRIVER_ENTER_PLATE
MSG_DRIVER_ENTER_LICENSE = RegistrationMessages.DRIVER_ENTER_LICENSE
MSG_DRIVER_REVIEW_TITLE = RegistrationMessages.DRIVER_REVIEW_TITLE
MSG_DRIVER_SUCCESS = SuccessMessages.DRIVER_SUBMISSION_SUCCESS
MSG_DRIVER_INVALID_PHONE = RegistrationMessages.INVALID_PHONE
MSG_DRIVER_INVALID_PLATE = RegistrationMessages.INVALID_PLATE
MSG_DRIVER_INVALID_LICENSE = RegistrationMessages.INVALID_LICENSE
MSG_DRIVER_INVALID_VEHICLE = RegistrationMessages.INVALID_VEHICLE

MSG_DRIVER_LIST_TITLE = "🚗 **Driver Records**\n\nSelect a driver to view and manage their profile:"
MSG_DRIVER_DETAIL_TITLE = "🚘 **Driver Record Detail**\n\n👤 **Name:** {full_name}\n📱 **Phone:** {phone_number}\n🪪 **License:** {license_number}\n🚗 **Vehicle:** {vehicle_type}\n🔢 **Plate:** {plate_number}\n📌 **Status:** {status}\n📡 **Availability:** {availability}\n⭐ **Rating:** {rating_avg}\n📦 **Deliveries:** {total_deliveries}"
MSG_DRIVER_EDIT_PROMPT = "✏️ **Edit Driver Record**\n\nSelect the field you want to update:"
MSG_DRIVER_EDIT_INPUT_PROMPT = "📝 **Update {field_label}**\n\nCurrent value: `{current_value}`\n\nPlease enter the new value:"
MSG_DRIVER_REMOVE_CONFIRM = "⚠️ **Remove Driver Record**\n\nAre you sure you want to remove driver **{full_name}**?\n\nThis action will:\n• Delete the driver profile\n• Remove driver role from the user\n• Log the action for audit\n\nThis cannot be undone."
MSG_DRIVER_REMOVE_CANCELLED = "🛑 Driver removal cancelled."

MSG_REQ_CONFIRM_HALL = RequestMessages.CONFIRM_HALL
MSG_REQ_ENTER_PICKUP_DETAIL = RequestMessages.ENTER_PICKUP_DETAIL
MSG_REQ_ENTER_DROPOFF_ADDRESS = RequestMessages.ENTER_DROPOFF_ADDRESS
MSG_REQ_ENTER_DROPOFF_LANDMARK = RequestMessages.ENTER_DROPOFF_LANDMARK
MSG_REQ_ENTER_RECIPIENT_NAME = RequestMessages.ENTER_RECIPIENT_NAME
MSG_REQ_ENTER_RECIPIENT_PHONE = RequestMessages.ENTER_RECIPIENT_PHONE
MSG_REQ_CHOOSE_LUGGAGE_SIZE = RequestMessages.CHOOSE_LUGGAGE_SIZE
MSG_REQ_ENTER_LUGGAGE_COUNT = RequestMessages.ENTER_LUGGAGE_COUNT
MSG_REQ_ENTER_PREFERRED_DATE = RequestMessages.ENTER_PREFERRED_DATE
MSG_REQ_CHOOSE_TIME_WINDOW = RequestMessages.CHOOSE_TIME_WINDOW
MSG_REQ_ENTER_SPECIAL_INSTRUCTIONS = RequestMessages.ENTER_SPECIAL_INSTRUCTIONS
MSG_REQ_REVIEW_TITLE = RequestMessages.REVIEW_TITLE
MSG_REQ_SUBMIT = "✅ Submit Request"
MSG_REQ_CREATED = SuccessMessages.REQUEST_CREATED
MSG_REQ_INVALID_PICKUP_DETAIL = "⚠️ Please provide a clear pickup location."
MSG_REQ_INVALID_DROPOFF_ADDRESS = "⚠️ Delivery address must be at least 10 characters long."
MSG_REQ_INVALID_RECIPIENT_NAME = "⚠️ Please enter the recipient's first and last name."
MSG_REQ_INVALID_RECIPIENT_PHONE = "⚠️ Please enter a valid Nigerian phone number."
MSG_REQ_INVALID_LUGGAGE_COUNT = "⚠️ Please enter a number between {min} and {max}."
MSG_REQ_INVALID_PREFERRED_DATE = "⚠️ Please pick today or a future date within {days} days."
MSG_EMPTY_STATE_REQUESTS = RequestMessages.EMPTY_STATE_STUDENT
MSG_EMPTY_STATE_DRIVER = RequestMessages.EMPTY_STATE_DRIVER

# Request status labels
MSG_STATUS_PENDING = "⏳ Pending"
MSG_STATUS_ASSIGNED = "👤 Assigned"
MSG_STATUS_ACCEPTED = "🤝 Accepted"
MSG_STATUS_REJECTED_BY_DRIVER = "❌ Rejected by Driver"
MSG_STATUS_EN_ROUTE_TO_PICKUP = "🚗 En Route to Pickup"
MSG_STATUS_PICKED_UP = "📦 Picked Up"
MSG_STATUS_IN_TRANSIT = "🛣️ In Transit"
MSG_STATUS_DELIVERED = "🎉 Delivered"
MSG_STATUS_CANCELLED = "🚫 Cancelled"
MSG_STATUS_FAILED = "⚠️ Delivery Failed"

# Notifications
MSG_NOTIFY_ADMIN_NEW_REQUEST = "🔔 **New Delivery Request!**\nSubmitted by: {student_name}"
MSG_NOTIFY_DRIVER_ASSIGNED = "🎯 **New Delivery Assignment!**\nYou've been assigned a new pickup."
MSG_NOTIFY_STUDENT_ASSIGNED = "🚗 **Driver Assigned!**\nA driver is now preparing to pick up your package."
MSG_NOTIFY_DRIVER_APPROVED = "🎉 **Congratulations!** Your driver application has been approved."
MSG_NOTIFY_DRIVER_REJECTED = "❌ **Application Update:** Your driver application was not approved."
MSG_NOTIFY_DELIVERY_COMPLETED = "🎊 **Package Delivered!** Your delivery is complete."
MSG_NOTIFY_REQUEST_CANCELLED = "ℹ️ Your delivery request has been cancelled."