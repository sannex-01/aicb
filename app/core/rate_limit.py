from slowapi import Limiter
from slowapi.util import get_remote_address

# Keyed by client IP: unlike every other inbound surface in this service
# (signed webhooks), /api/v1/widget/* is reachable directly from arbitrary
# third-party browser JS with no per-request auth — session_id is client-
# supplied and trivially spoofable, so IP is the real defense here.
limiter = Limiter(key_func=get_remote_address)
