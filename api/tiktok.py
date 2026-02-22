import hashlib
import time
import httpx
import logging
import database
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIKTOK_API_URL = "https://business-api.tiktok.com/open_api/v1.3/event/track/"

def hash_value(value: Optional[str]) -> Optional[str]:
    """Hashes a value using SHA256 as required by TikTok (lowercase first)."""
    if not value:
        return None
    return hashlib.sha256(str(value).strip().lower().encode('utf-8')).hexdigest()

async def send_tiktok_event(
    event_name: str,
    user_id: int,
    user_data: Dict[str, Any],
    properties: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None
):
    """
    Sends a server-side event to TikTok Ads API.
    """
    access_token = database.get_setting("tiktok_api_token")
    pixel_id = database.get_setting("tiktok_pixel_id")

    if not access_token or not pixel_id:
        logger.warning("TikTok Ads API not configured. Skipping event.")
        return

    # Extract tracking data
    tracking = user_data.get("tracking_data") or {}
    ttclid = tracking.get("ttclid")

    # Prepare user identifiers
    # For Telegram, we usually don't have email/phone unless asked, 
    # but we use hashed user_id as external_id.
    user_payload = {
        "external_id": hash_value(str(user_id)),
        "ip": user_data.get("ip"),
        "user_agent": user_data.get("user_agent") or "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    }

    if user_data.get("email"):
        user_payload["email"] = hash_value(user_data["email"])
    if user_data.get("phone"):
        user_payload["phone_number"] = hash_value(user_data["phone"])
    if ttclid:
        user_payload["ttclid"] = ttclid

    # Event Payload
    payload = {
        "pixel_code": pixel_id,
        "event": event_name,
        "event_id": event_id or f"evt_{user_id}_{int(time.time())}",
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "context": {
            "ad": {"callback": ttclid} if ttclid else {},
            "user": user_payload
        },
        "properties": properties or {}
    }

    headers = {
        "Access-Token": access_token,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"TikTok API Request: {event_name} for user {user_id}")
            response = await client.post(TIKTOK_API_URL, json=payload, headers=headers)
            result = response.json()
            
            if response.status_code != 200 or result.get("code") != 0:
                logger.error(f"TikTok API Error: {response.status_code} - {result.get('message')} (Code: {result.get('code')})")
            else:
                logger.info(f"TikTok Event Sent Successfully: {event_name}")
        except Exception as e:
            logger.error(f"TikTok Connection Error: {e}")
