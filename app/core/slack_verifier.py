"""
Slack Request Verification
Verifies X-Slack-Signature using HMAC-SHA256 and SLACK_SIGNING_SECRET.
https://api.slack.com/authentication/verifying-requests-from-slack
"""

import hashlib
import hmac
import time
from typing import Optional

from fastapi import Request, HTTPException

from app.core.settings import settings


_REPLAY_WINDOW_SECONDS = 300  # 5 minutes — Slack's own replay-attack window


async def verify_slack_signature(request: Request) -> bytes:
    """
    Validate the X-Slack-Signature header on an inbound Slack request.

    Returns the raw request body (already consumed) so callers can parse it.
    Raises HTTPException(403) if the signature is missing, stale, or invalid.
    """
    signing_secret: Optional[str] = settings.SLACK_SIGNING_SECRET
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not configured")

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Reject requests older than 5 minutes (replay-attack guard)
    try:
        ts = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=403, detail="Missing or invalid timestamp")

    if abs(time.time() - ts) > _REPLAY_WINDOW_SECONDS:
        raise HTTPException(status_code=403, detail="Request timestamp is too old")

    body: bytes = await request.body()

    # Compute expected signature
    base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    return body
