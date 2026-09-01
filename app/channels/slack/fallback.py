from app.core.config import settings

def get_support_contact_message() -> str:
    """Returns a friendly direct contact card when human agent handoff is requested."""
    return (
        f"👨‍💼 Our live support team is available to help you directly!\n\n"
        f"📞 Phone / WhatsApp: {settings.SUPPORT_PHONE_NUMBER}\n"
        f"✉️ Email: {settings.SUPPORT_EMAIL}\n\n"
        f"An agent has also been notified and will follow up shortly."
    )
