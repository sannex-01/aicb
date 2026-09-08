"""Delivery address collection: a single free-text message on Telegram/
WhatsApp, parsed into structured fields, versus a real form on the website
widget. See FlowEngine's address_collect state machine (app/flows/engine.py)
for the chat-driven flow this module supports, and app/channels/widget for
the structured-form path.

Nigeria-first, matching this codebase's existing NGN/CURRENCY_METADATA
assumption (app/services/payments.py) rather than a full generic
international reference table — extend NIGERIAN_STATES/SUPPORTED_COUNTRIES
if/when a real second market is added.
"""
import re
from typing import Dict, List, Optional, Tuple

NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi",
    "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun",
    "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
]

# Common informal spellings/abbreviations a customer might actually type.
_STATE_ALIASES = {
    "abuja": "FCT", "fct abuja": "FCT", "federal capital territory": "FCT",
    "akwa-ibom": "Akwa Ibom", "cross-river": "Cross River",
}

SUPPORTED_COUNTRIES = ["Nigeria", "Ghana", "Kenya", "South Africa"]

_STATE_LOOKUP = {s.lower(): s for s in NIGERIAN_STATES}
_STATE_LOOKUP.update(_STATE_ALIASES)
_COUNTRY_LOOKUP = {c.lower(): c for c in SUPPORTED_COUNTRIES}
_COUNTRY_LOOKUP["nig"] = "Nigeria"
_COUNTRY_LOOKUP["ng"] = "Nigeria"


def match_state(value: str) -> Optional[str]:
    return _STATE_LOOKUP.get(value.strip().lower())


def match_country(value: str) -> Optional[str]:
    return _COUNTRY_LOOKUP.get(value.strip().lower())


REQUIRED_FIELDS = ["street", "city", "state", "country", "zip"]

ADDRESS_TEMPLATE_HINT = (
    "Please send your delivery address as one message, in this order, separated by commas:\n\n"
    "*Street address, City, State, Zip/Postal code, Country*\n\n"
    "Example: _12 Adeola Street, Ikeja, Lagos, 100281, Nigeria_"
)


# A zip/postal code segment, when present, looks like digits (optionally
# with a letter or two, for non-Nigerian formats) 3-8 chars long — used to
# spot it among the remaining comma segments after country/state are
# pulled off, since its position isn't fixed the way country/state are.
_ZIP_LIKE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\s-]{2,9}$")


def _looks_like_zip(segment: str) -> bool:
    stripped = segment.strip()
    if not stripped or len(stripped) > 10:
        return False
    digit_count = sum(1 for c in stripped if c.isdigit())
    return digit_count >= 3 and bool(_ZIP_LIKE_RE.match(stripped))


def parse_free_text_address(text: str) -> Tuple[Dict[str, Optional[str]], List[str]]:
    """Splits a comma-separated free-text address into fields, matching
    country and state against our known lists (case-insensitive, common
    aliases).

    Positional convention, rightmost first (per the user-directed design —
    zip's position isn't fixed the way country/state are, since Nigerian
    addresses often omit it or place it inconsistently):
      1. last segment = country (matched against SUPPORTED_COUNTRIES)
      2. second-to-last (of what remains) = state (matched against
         NIGERIAN_STATES)
      3. of what remains, the last segment is popped as zip ONLY if it
         looks like a postal code (mostly digits, short) — otherwise no zip
         segment is assumed and it's left for the customer to add if needed
      4. of what remains, the last segment = city
      5. everything left (rejoined with commas) = street

    Returns (fields, missing_field_names). A field lands in
    `missing_field_names` when there weren't enough comma-separated
    segments to fill it, OR (state/country specifically) what was typed
    didn't match our known list — the customer is then asked for just that
    one field rather than resending the whole address.

    Known limitation: this is a positional parser, not real NLP. Since
    state/country sit at FIXED positions from the end, a typo or unexpected
    value in state (e.g. "Lagoss") also knocks the zip detection below it
    out of alignment — both land in missing_field_names and get asked one
    at a time, which is safe (never silently misattributes a field) but
    means one mistake can cost the customer two follow-up questions instead
    of one. Good enough for the common case (state/country spelled
    correctly), not a substitute for a real address-autocomplete API."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    fields: Dict[str, Optional[str]] = {k: None for k in REQUIRED_FIELDS}
    missing: List[str] = []

    if len(parts) >= 1:
        matched_country = match_country(parts[-1])
        if matched_country:
            fields["country"] = matched_country
            parts = parts[:-1]
        else:
            missing.append("country")
    else:
        missing.append("country")

    if len(parts) >= 1:
        matched_state = match_state(parts[-1])
        if matched_state:
            fields["state"] = matched_state
            parts = parts[:-1]
        else:
            missing.append("state")
    else:
        missing.append("state")

    if len(parts) >= 1 and _looks_like_zip(parts[-1]):
        fields["zip"] = parts[-1]
        parts = parts[:-1]
    else:
        missing.append("zip")

    if len(parts) >= 1:
        fields["city"] = parts[-1]
        parts = parts[:-1]
    else:
        missing.append("city")

    if parts:
        fields["street"] = ", ".join(parts)
    else:
        missing.append("street")

    return fields, missing


def format_address_confirmation(fields: Dict[str, Optional[str]]) -> str:
    return (
        f"• *Street:* {fields.get('street') or '[Not Set]'}\n"
        f"• *City:* {fields.get('city') or '[Not Set]'}\n"
        f"• *State:* {fields.get('state') or '[Not Set]'}\n"
        f"• *Zip/Postal Code:* {fields.get('zip') or '[Not Set]'}\n"
        f"• *Country:* {fields.get('country') or '[Not Set]'}"
    )


def address_to_single_line(fields: Dict[str, Optional[str]]) -> str:
    """Collapses structured fields back into the one-line string
    Order.shipping_address (and Bumpa's shipping_context_from_address,
    which only has a single street field to build on) currently expect —
    kept for backwards compatibility with that single-string column while
    the STRUCTURED fields (see Customer.metadata_json["delivery_address"])
    are what powers real Bumpa shipping-options lookups going forward."""
    parts = [fields.get("street"), fields.get("city"), fields.get("state"), fields.get("zip"), fields.get("country")]
    return ", ".join(p for p in parts if p)
