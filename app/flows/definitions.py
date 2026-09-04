from typing import Dict, Any, List

MAIN_MENU_BUTTONS = [
    {"id": "flow_browse_catalog", "title": "🛍️ Browse Products"},
    {"id": "flow_view_cart", "title": "🛒 View Cart"},
    {"id": "flow_track_order", "title": "📦 Track Order"},
    {"id": "flow_my_profile", "title": "👤 My Profile"},
]

CART_BUTTONS = [
    {"id": "flow_checkout", "title": "💳 Checkout Now"},
    {"id": "flow_browse_catalog", "title": "🛍️ Add More Items"},
    {"id": "flow_clear_cart", "title": "🗑️ Clear Cart"},
]

CART_EMPTY_BUTTONS = [
    {"id": "flow_browse_catalog", "title": "🛍️ Browse Products"},
    {"id": "flow_main_menu", "title": "🏠 Main Menu"},
]

def get_main_menu_text() -> str:
    return (
        "👋 Welcome! How can we help you today?\n\n"
        "Please select an option from the buttons below:"
    )
