"""OneKhusa configuration.

Config-driven like config/onekhusa.php in the Laravel project: all credentials,
endpoints, and app settings are resolved from environment variables
(see .env / .env.example). No hardcoded values in app code.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    """Read an integer from the environment, falling back to `default`."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# -- App settings -----------------------------------------------------------
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "1").lower() in {"1", "true", "yes"}
PORT = _env_int("PORT", 8080)
DEFAULT_AMOUNT = 2500
DEFAULT_DESCRIPTION = "OneTicket Python Purchase"
STATUS_TTL = 1800  # seconds the status cache keeps an entry

# -- Credentials (from the OneKhusa merchant portal) ------------------------
ONEKHUSA_API_KEY = os.getenv("ONEKHUSA_API_KEY", "")
ONEKHUSA_API_SECRET = os.getenv("ONEKHUSA_API_SECRET", "")
ONEKHUSA_ORG_ID = os.getenv("ONEKHUSA_ORG_ID", "")
ONEKHUSA_MERCHANT_NUMBER = _env_int("ONEKHUSA_MERCHANT_NUMBER", 0)

# -- Endpoints --------------------------------------------------------------
# Get Access Token endpoint - returns JWT used as 'Authorization: Bearer <token>'
ONEKHUSA_TOKEN_URL = os.getenv(
    "ONEKHUSA_TOKEN_URL",
    "https://api.onekhusa.com/sandbox/v1/account/getAccessToken",
)

# Hosted checkout initiate endpoint - returns paymentTransactionId
ONEKHUSA_CHECKOUT_URL = os.getenv(
    "ONEKHUSA_CHECKOUT_URL",
    "https://api.onekhusa.com/sandbox/v1/checkout/rtp/initiate",
)

# Hosted checkout page (redirect target after successful initiation)
ONEKHUSA_CHECKOUT_REDIRECT_URL = os.getenv(
    "ONEKHUSA_CHECKOUT_REDIRECT_URL",
    "https://checkout.onekhusa.com/requestToPay/initiate",
)

# -- Public callback URL ----------------------------------------------------
# A publicly reachable URL (e.g. an ngrok tunnel) that OneKhusa uses to
# redirect customers back and to deliver webhook callbacks to this app.
PUBLIC_CALLBACK_URL = os.getenv("PUBLIC_CALLBACK_URL", "")
