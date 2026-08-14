"""OneKhusa Hosted Checkout — Flask demo.

Mirrors the Laravel project:
  - routes/web.php  -> GET  "/"                          (dashboard)
  - routes/api.php  -> POST /api/Tickets/buy/{eventId}   (initiate)
                    -> GET  /api/Tickets/status/{ref}    (poll)
                    -> POST /api/webhooks/payments       (webhook)
  - TicketController / WebhookController -> route handlers below
"""

import logging
import time

from flask import Flask, jsonify, render_template, request

import config
from services.onekhusa_service import OneKhusaError, OneKhusaService
from status_cache import status_cache

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

onekhusa = OneKhusaService()


# ---------------------------------------------------------------------------
# Page (routes/web.php)
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("welcome.html")


# ---------------------------------------------------------------------------
# Hosted checkout API (routes/api.php + TicketController)
# ---------------------------------------------------------------------------
@app.post("/api/Tickets/buy/<event_id>")
def buy(event_id: str):
    """Initiate a hosted checkout payment and return the redirect URL.

    `event_id` is part of the URL for parity with the Laravel project
    (`/api/Tickets/buy/{eventId}`); payment details come from the request body.
    """
    data = request.get_json(silent=True) or {}
    reference = data.get("reference") or f"OT-PY-{int(time.time())}"
    description = data.get("description", config.DEFAULT_DESCRIPTION)

    try:
        amount = float(data.get("amount", config.DEFAULT_AMOUNT))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid amount."}), 400

    try:
        result = onekhusa.initiate_checkout(amount, reference, description)

        # Persist the pending status so the frontend can poll for the result.
        status_cache.put(f"status_{reference}", "Pending", config.STATUS_TTL)

        return jsonify(
            {
                "status": "success",
                "reference": reference,
                "paymentTransactionId": result["paymentTransactionId"],
                "redirectUrl": onekhusa.checkout_redirect_url(
                    result["paymentTransactionId"]
                ),
            }
        )
    except (OneKhusaError, KeyError) as exc:
        app.logger.error("Checkout initiation failed: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.get("/api/Tickets/status/<reference>")
def status(reference: str):
    """Return the recorded status for a reference.

    Statuses: Pending | Paid | Failed | NotFound
    """
    return jsonify({"status": status_cache.get(f"status_{reference}", "NotFound")})


# ---------------------------------------------------------------------------
# OneKhusa webhook (WebhookController)
# ---------------------------------------------------------------------------
@app.post("/api/webhooks/payments")
def webhook():
    """Handle payment webhooks from OneKhusa (payrequest.success).

    Must ALWAYS respond with HTTP 200-OK as acknowledgement of payload receipt.
    """
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    app.logger.info("OneKhusa webhook received: %s", payload)

    my_ref = resolve_reference(payload)
    if not my_ref:
        # Cannot correlate this payload to a known transaction, but still
        # acknowledge so OneKhusa does not retry forever.
        app.logger.warning("OneKhusa webhook without resolvable reference: %s", payload)
        return "acknowledged", 200

    event = resolve_event(payload)
    new_status = "Paid" if is_success(payload, event) else "Failed"
    status_cache.put(f"status_{my_ref}", new_status, config.STATUS_TTL)
    app.logger.info("OneKhusa: status updated to %s for %s", new_status.upper(), my_ref)

    return "acknowledged", 200


# ---------------------------------------------------------------------------
# Webhook helpers
# ---------------------------------------------------------------------------
def resolve_reference(payload: dict) -> str | None:
    """Resolve our reference number from a webhook payload.

    OneKhusa may nest it in `metaData` with TitleCase keys, or expose it at
    the top level.
    """
    metadata = payload.get("metaData") or {}
    return (
        metadata.get("ReferenceNumber")
        or metadata.get("referenceNumber")
        or payload.get("sourceReferenceNumber")
        or payload.get("referenceNumber")
        or (payload.get("payment") or {}).get("sourceReferenceNumber")
    )


def resolve_event(payload: dict) -> str:
    """Resolve the webhook event name from common payload fields."""
    return str(
        payload.get("eventType")
        or payload.get("event")
        or payload.get("type")
        or payload.get("eventName")
        or payload.get("notificationType")
        or ""
    ).lower()


def is_success(payload: dict, event: str = "") -> bool:
    """Detect a successful payment payload (payrequest.success)."""
    response_code = str(payload.get("responseCode") or "")
    status_code = str(payload.get("transactionStatusCode") or "").upper()
    return (
        "success" in event
        or response_code == "S100"
        or status_code == "S"
        or response_code.startswith("S")
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=config.FLASK_DEBUG)
