import os
import httpx
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UTMFY_WEBHOOK_URL = os.getenv("UTMFY_WEBHOOK_URL")

async def send_event(event_name: str, user_data: Dict[str, Any], transaction_data: Optional[Dict[str, Any]] = None):
    """
    Sends a tracking event to UTMfy.
    """
    if not UTMFY_WEBHOOK_URL:
        logger.warning("UTMFY_WEBHOOK_URL not configured. Skipping event.")
        return

    payload = {
        "event": event_name,
        "user": user_data,
        "timestamp": user_data.get("created_at")
    }
    
    if transaction_data:
        payload["transaction"] = transaction_data

    # Add browser/tracking data if available
    tracking_keys = ["ttclid", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]
    for key in tracking_keys:
        if key in user_data:
            payload[key] = user_data[key]

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending event '{event_name}' to UTMfy for user {user_data.get('id')}")
            response = await client.post(UTMFY_WEBHOOK_URL, json=payload)
            if response.status_code not in [200, 201]:
                logger.error(f"UTMfy API Error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"UTMfy Connection Error: {e}")
