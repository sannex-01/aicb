from typing import Dict, Any, List

MAIN_MENU_BUTTONS = [
    {"id": "flow_browse_catalog", "title": "🛍️ Browse Products"},
    {"id": "flow_track_order", "title": "📦 Track Order"},
    {"id": "flow_contact_support", "title": "💬 Talk to Human"},
]

def get_main_menu_text() -> str:
    return (
        "👋 Welcome! How can we help you today?\n\n"
        "Please select an option from the buttons below:"
    )
