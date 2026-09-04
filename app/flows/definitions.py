from typing import Dict, Any, List

MAIN_MENU_BUTTONS = [
    {"id": "flow_browse_catalog", "title": "🛍️ Browse Products"},
    {"id": "flow_view_cart", "title": "🛒 View Cart"},
    {"id": "flow_track_order", "title": "📦 Track Order"},
    {"id": "flow_my_profile", "title": "👤 My Profile"},
]

CART_BUTTONS = [
    {"id": "flow_checkout", "title": "💳 Checkout Now"},
    {"id": "flow_browse_catalog", "title": "🛍️ Add More Products"},
    {"id": "flow_clear_cart", "title": "🗑️ Clear Cart"},
    {"id": "flow_main_menu", "title": "🏠 Menu"},
]

CART_EMPTY_BUTTONS = [
    {"id": "flow_browse_catalog", "title": "🛍️ Browse Products"},
    {"id": "flow_main_menu", "title": "🏠 Main Menu"},
]

def get_quantity_buttons(product_id: int, current_qty: int = 1) -> List[Dict[str, str]]:
    """Generates preset quantity selection buttons and navigation buttons."""
    return [
        {"id": f"qty_set_{product_id}_1", "title": "1️⃣ Qty: 1" if current_qty != 1 else "✅ 1"},
        {"id": f"qty_set_{product_id}_2", "title": "2️⃣ Qty: 2" if current_qty != 2 else "✅ 2"},
        {"id": f"qty_set_{product_id}_3", "title": "3️⃣ Qty: 3" if current_qty != 3 else "✅ 3"},
        {"id": f"qty_set_{product_id}_5", "title": "5️⃣ Qty: 5" if current_qty != 5 else "✅ 5"},
        {"id": f"qty_set_{product_id}_10", "title": "🔟 Qty: 10" if current_qty != 10 else "✅ 10"},
        {"id": "flow_view_cart", "title": "🛒 Go to Cart"},
        {"id": "flow_checkout", "title": "💳 Checkout Now"},
        {"id": "flow_browse_catalog", "title": "🛍️ Add More Products"},
    ]

def get_main_menu_text() -> str:
    return (
        "👋 Welcome! How can we help you today?\n\n"
        "Please select an option from the buttons below:"
    )
