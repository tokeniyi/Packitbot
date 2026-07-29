MSG_START_ROLE_SELECTION = "Welcome to Packitbot! Are you a Student or a Driver?"

# Admins
MSG_START_ADMIN_WELCOME = (
    "⚙️ **Admin Portal Active**\n\n"
    "Welcome back, Boss! You have full administrative access.\n\n"
    "🛠️ **Quick Actions:**\n"
    "• View active dispatch orders\n"
    "• Manage verified drivers & students\n"
    "• System metrics & logs\n\n"
    "Type /admin to open the management panel."
)

MSG_MANAGEMENT_PORTAL = (
    "⚙️ **Admin Management Panel**\n\n"
    "Welcome, Admin! Here are the commands and controls available to you:\n\n"
    "📊 **System & Metrics**\n"
    "• `/admin` — Re-open this management portal\n"
    "• `/stats` — View live delivery metrics & system stats\n\n"
    "👥 **User & Verification Management**\n"
    "• `/verify` — Review & verify pending driver accounts\n"
    "• `/users` — Search or view registered students and drivers\n\n"
    "📦 **Logistics & Orders**\n"
    "• `/orders` — View active, pending, or completed deliveries\n"
    "• `/broadcast` — Send an announcement message to all users\n\n"
    "💡 *Tip: You can also use the inline buttons below to navigate quick actions!(not implemented yet 😁*"
)

MSG_STATS = (
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


MSG_START_ROLE_SELECTION_STUDENT = "📚 Student"
MSG_START_ROLE_SELECTION_DRIVER = "🚗 Driver"



from bot.core.config import get_support_url

SUPPORT_LINK = get_support_url()

MSG_HELP = (
    "👋 **Need help getting started?**\n\n"
    "📦 **Packitbot** connects Covenant University students with trusted drivers "
    "for fast, reliable campus deliveries.\n\n"
    "💡 **Quick Tips:**\n"
    "• Use the menu buttons below to navigate.\n"
    "• Type /start or /home anytime to return to the main menu.\n"
    "• Want to reset or start over? Just send /cancel!\n\n"
    f"💬 **Having any issues?** [Contact Support Directly]({SUPPORT_LINK})"
)



MSG_ABOUT = (
    "🚀 **Packitbot** — CU delivery logistics, simplified.\n\n"
    "🎓 **Students** request deliveries.\n"
    "🚗 **Drivers** accept & complete them.\n"
    "⚙️ **Admins** keep everything running smoothly!\n\n"
    "👋 New here or ran into an issue? Type /help for quick support, "
    "or send /menu to explore all the things you can do!"
)


MSG_WELCOME_GENERAL = (
    "👋 Welcome to **Packitbot**!\n\n"
    "The easiest way to send and receive packages on Covenant University campus.\n\n"
    "🎓 **Students:** Send items to friends or family on campus.\n"
    "🚗 **Drivers:** Earn money by delivering packages.\n"
    "⚙️ **Admins:** Keep the system running smoothly.\n\n"
    "Ready to get started?"
)


# Student registration flow
MSG_STUDENT_WELCOME = (
    "🎓 **Welcome to the Student Portal!**\n\n"
    "We're ready whenever you are! 📦\n\n"
    "🚀 **Get Started**\n"
    "• /request — Create a new delivery request\n"
    "• /my_requests — View and track your requests\n\n"
    "⚙️ Want to update your profile? Send /menu to open your profile and settings."
)


MSG_REG_STEP_PROMPT = "📌 **Step {current} of {total}** {progress_bar}\n\n{prompt}"
MSG_REG_ENTER_FULL_NAME = "👤 **What's your full name?**\n*(e.g., John Doe)*"
MSG_REG_ENTER_MATRIC = "🪪 **Enter your matriculation number.**\n*(e.g., 21AB1234)*"
MSG_REG_ENTER_HALL = "🏛️ **Which hall of residence do you live in?**"
MSG_REG_ENTER_PHONE = "📱 **Share your phone number so drivers can reach you.**"
MSG_REG_REVIEW_TITLE = "📋 **Let's confirm your details:**"
MSG_REG_EDIT = "✏️ Edit"
MSG_REG_SUBMIT = "✅ Submit"
MSG_REG_SUCCESS = "🎉 **Registration complete!** You can now create delivery requests."
MSG_REG_INVALID_FULL_NAME = "⚠️ Please enter your full name (first and last name)."
MSG_REG_INVALID_MATRIC = "⚠️ That doesn't look like a valid matric number. Please try again."
MSG_REG_INVALID_PHONE = "⚠️ Please enter a valid 11-digit Nigerian phone number."
MSG_DRIVER_NOT_APPROVED = (
    "🚗 **Driver Access Restricted**\n\n"
    "Only approved drivers can select this role.\n"
    "Please contact an admin to request driver approval!"
)

# Driver registration flow
MSG_DRIVER_WELCOME = "🚗 **Driver Portal**\n\nReady to earn by delivering? Let's get you set up!"


MSG_DRIVER_PENDING_APPROVAL = (
    "⏳ **Application Pending Review**\n\n"
    "Your driver profile has been created and is waiting for admin approval.\n"
    "We'll notify you as soon as an admin approves your profile!"
)
MSG_DRIVER_STEP_PROMPT = "📌 **Step {current} of {total}** {progress_bar}\n\n{prompt}"
MSG_DRIVER_ENTER_FULL_NAME = "👤 **What's your full name?**"
MSG_DRIVER_ENTER_PHONE = "📱 **Share your phone number.**"
MSG_DRIVER_CHOOSE_VEHICLE = "🚘 **What type of vehicle do you drive?**"
MSG_DRIVER_ENTER_PLATE = "🔤 **Enter your vehicle plate number.**"
MSG_DRIVER_ENTER_LICENSE = "🪪 **Enter your driver's license number.**"
MSG_DRIVER_REVIEW_TITLE = "📋 **Confirm your driver details:**"
MSG_DRIVER_SUCCESS = "⏳ **Application submitted!** An admin will review your profile shortly."
MSG_DRIVER_INVALID_PHONE = "⚠️ Please enter a valid 11-digit Nigerian phone number."
MSG_DRIVER_INVALID_PLATE = "⚠️ Please enter a valid plate number."
MSG_DRIVER_INVALID_LICENSE = "⚠️ Please enter a valid license number."
MSG_DRIVER_INVALID_VEHICLE = "⚠️ Please select a vehicle type from the buttons."

# Request creation flow
MSG_REQ_CONFIRM_HALL = "📍 **Pickup Location:** {hall}\nDo you want to use this location?"
MSG_REQ_ENTER_PICKUP_DETAIL = "📍 **Where should the driver meet you?**\n*(e.g., Hostel Block B, Room 12)*"
MSG_REQ_ENTER_DROPOFF_ADDRESS = "🎯 **Where should the driver deliver this package?**"
MSG_REQ_ENTER_DROPOFF_LANDMARK = "🗺️ **Any nearby landmark?** *(optional, send 'Skip' if none)*"
MSG_REQ_ENTER_RECIPIENT_NAME = "👤 **Who is receiving this package?**"
MSG_REQ_ENTER_RECIPIENT_PHONE = "📱 **What's the recipient's phone number?**"
MSG_REQ_CHOOSE_LUGGAGE_SIZE = "📦 **How big is the item/luggage?**"
MSG_REQ_ENTER_LUGGAGE_COUNT = "🔢 **How many items are you sending ({min}-{max})?**"
MSG_REQ_ENTER_PREFERRED_DATE = "📅 **When should this be picked up?**"
MSG_REQ_CHOOSE_TIME_WINDOW = "⏰ **Pick a preferred time window:**"
MSG_REQ_ENTER_SPECIAL_INSTRUCTIONS = "📝 **Any special instructions for the driver?** *(optional)*"
MSG_REQ_REVIEW_TITLE = "🧾 **Review your delivery request:**"
MSG_REQ_SUBMIT = "✅ Submit Request"
MSG_REQ_CREATED = "🚀 **Request submitted!** We'll notify you as soon as a driver accepts."
MSG_REQ_INVALID_PICKUP_DETAIL = "⚠️ Please provide a clear pickup location."
MSG_REQ_INVALID_DROPOFF_ADDRESS = "⚠️ Delivery address must be at least 10 characters long."
MSG_REQ_INVALID_RECIPIENT_NAME = "⚠️ Please enter the recipient's first and last name."
MSG_REQ_INVALID_RECIPIENT_PHONE = "⚠️ Please enter a valid Nigerian phone number."
MSG_REQ_INVALID_LUGGAGE_COUNT = "⚠️ Please enter a number between {min} and {max}."
MSG_REQ_INVALID_PREFERRED_DATE = "⚠️ Please pick today or a future date within {days} days."

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
MSG_BROADCAST_SENT = "📢 **Broadcast sent successfully** to {count} users."

# Generic / shared
MSG_SOMETHING_WENT_WRONG = "❌ Something went wrong. Please try again."
MSG_NO_PERMISSION = "⛔ You don't have permission to perform this action."
MSG_INVALID_INPUT = "🤔 That input doesn't look right. Please try again."
MSG_ACTION_CONFIRMED = "✅ Done!"
MSG_ACTION_CANCELLED = "🛑 Action cancelled."
MSG_EMPTY_STATE_REQUESTS = "📭 You haven't created any delivery requests yet.\nTap **📦 New Request** to get started!"
MSG_EMPTY_STATE_DRIVER = "🛋️ You don't have an active delivery right now. We'll notify you when a request comes in!"
MSG_SLOW_DOWN = "⏳ **Slow down!** You're tapping buttons too fast."
MSG_BANNED = "🔒 **Account Restricted.** Your account has been restricted. Contact an admin for assistance."


# welcome admin