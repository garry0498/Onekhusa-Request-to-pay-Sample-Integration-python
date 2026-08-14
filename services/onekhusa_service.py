"""Thin wrapper around the OneKhusa Payment Gateway API.

Mirrors app/Services/OneKhusaService.php from the Laravel project.

Supports the Hosted Checkout flow:
  - Obtain a short-lived access token (JWT) via /account/getAccessToken
  - Initiate a payment (/checkout/rtp/initiate), which returns a
    paymentTransactionId used to redirect the customer to the managed
    checkout page.
"""

import secrets
import time
from urllib.parse import urlencode

import requests

import config

REQUEST_TIMEOUT = 30  # seconds


class OneKhusaError(RuntimeError):
    """Raised when the OneKhusa API returns an error."""


class OneKhusaService:
    """Access tokens live for 5 minutes; cache them for 4 to stay safe."""

    TOKEN_CACHE_TTL = 240  # seconds

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # Access token
    # ------------------------------------------------------------------
    def get_access_token(self) -> str:
        """Return a valid access token (JWT) used as `Authorization: Bearer`."""
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token

        try:
            response = requests.post(
                config.ONEKHUSA_TOKEN_URL,
                json={
                    "apiKey": config.ONEKHUSA_API_KEY,
                    "apiSecret": config.ONEKHUSA_API_SECRET,
                    "organisationId": config.ONEKHUSA_ORG_ID,
                    "merchantAccountNumber": config.ONEKHUSA_MERCHANT_NUMBER,
                },
                headers={"Accept-Language": "en"},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise OneKhusaError(f"OneKhusa token error: {exc}") from exc

        self._throw_if_failed(response, "token")

        token = response.json().get("accessToken")
        if not token:
            raise OneKhusaError("OneKhusa token error: no accessToken returned.")

        self._token = token
        self._token_expires_at = now + self.TOKEN_CACHE_TTL
        return token

    # ------------------------------------------------------------------
    # Hosted checkout
    # ------------------------------------------------------------------
    def initiate_checkout(
        self,
        amount: float,
        reference: str,
        description: str | None = None,
    ) -> dict:
        """Initiate a hosted checkout payment.

        POST /checkout/rtp/initiate
        Returns the initiation response containing `paymentTransactionId`,
        used to redirect the customer to the hosted checkout page.
        """
        callback_base = config.PUBLIC_CALLBACK_URL

        payload = {
            "authentication": self._authentication(),
            "merchant": self._merchant(),
            "payment": {
                "sourceReferenceNumber": reference,
                "description": description or config.DEFAULT_DESCRIPTION,
                "amount": amount,
            },
            "route": {
                "successRedirectionUrl": f"{callback_base}/?ref={reference}",
                "failureRedirectionUrl": f"{callback_base}/?ref={reference}&failed=1",
                "callbackApiUrl": f"{callback_base}/api/webhooks/payments",
            },
        }

        return self._post(config.ONEKHUSA_CHECKOUT_URL, payload, "checkout")

    def checkout_redirect_url(self, payment_transaction_id: str) -> str:
        """Build the redirect URL for a given payment transaction."""
        params = urlencode({"ptid": payment_transaction_id})
        return f"{config.ONEKHUSA_CHECKOUT_REDIRECT_URL}?{params}"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _authentication(self) -> dict:
        return {
            "apiKey": config.ONEKHUSA_API_KEY,
            "apiSecret": config.ONEKHUSA_API_SECRET,
        }

    def _merchant(self) -> dict:
        return {
            "organisationId": config.ONEKHUSA_ORG_ID,
            "merchantAccountNumber": config.ONEKHUSA_MERCHANT_NUMBER,
        }

    def _post(self, url: str, payload: dict, context: str) -> dict:
        headers = self._headers()
        headers["X-Idempotency-Key"] = f"PY-{context}-{secrets.token_hex(4)}"

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as exc:
            raise OneKhusaError(f"OneKhusa {context} error: {exc}") from exc

        self._throw_if_failed(response, context)

        try:
            return response.json() or {}
        except ValueError as exc:
            raise OneKhusaError(
                f"OneKhusa {context} error: invalid JSON response."
            ) from exc

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Accept-Language": "en",
        }

    @staticmethod
    def _throw_if_failed(response, context: str) -> None:
        if not response.ok:
            raise OneKhusaError(f"OneKhusa {context} error: {response.text}")
