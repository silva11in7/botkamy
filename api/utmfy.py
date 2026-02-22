import os
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UTMFY_API_TOKEN = os.getenv("UTMFY_API_TOKEN")
UTMFY_API_URL = "https://api.utmify.com.br/api-credentials/orders"

async def send_order(
    order_id: str,
    status: str,
    user_data: Dict[str, Any],
    product_data: Dict[str, Any],
    tracking_data: Optional[Dict[str, Any]] = None,
    payment_method: str = "pix",
    approved_date: Optional[str] = None
):
    """
    Sends order information to UTMfy Orders API.
    """
    if not UTMFY_API_TOKEN:
        logger.warning("UTMFY_API_TOKEN not configured. Skipping event.")
        return

    # Map status
    # waiting_payment | paid | refused | refunded | chargedback
    status_map = {
        "waiting": "waiting_payment",
        "pending": "waiting_payment",
        "paid": "paid",
        "confirmed": "paid",
        "refused": "refused",
        "refunded": "refunded"
    }
    utmify_status = status_map.get(status.lower(), "waiting_payment")

    # Format dates
    now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    payload = {
        "orderId": order_id,
        "platform": "KamyBot",
        "paymentMethod": payment_method,
        "status": utmify_status,
        "createdAt": user_data.get("created_at") or now_utc,
        "approvedDate": approved_date if utmify_status == "paid" else None,
        "refundedAt": None,
        "customer": {
            "name": user_data.get("full_name", "Telegram User"),
            "email": user_data.get("email") or f"user_{user_data.get('id')}@telegram.com",
            "phone": str(user_data.get("id")),
            "document": None,
            "country": "BR"
        },
        "products": [
            {
                "id": product_data.get("id", "vip"),
                "name": product_data.get("name", "Acesso VIP"),
                "planId": None,
                "planName": None,
                "quantity": 1,
                "priceInCents": int(product_data.get("price", 0) * 100)
            }
        ],
        "trackingParameters": {
            "src": None,
            "sck": None,
            "utm_source": tracking_data.get("utm_source") if tracking_data else None,
            "utm_medium": tracking_data.get("utm_medium") if tracking_data else None,
            "utm_campaign": tracking_data.get("utm_campaign") if tracking_data else None,
            "utm_content": tracking_data.get("utm_content") if tracking_data else None,
            "utm_term": tracking_data.get("utm_term") if tracking_data else None
        },
        "commission": {
            "totalPriceInCents": int(product_data.get("price", 0) * 100),
            "gatewayFeeInCents": 0,
            "userCommissionInCents": int(product_data.get("price", 0) * 100)
        },
        "isTest": False
    }

    headers = {
        "x-api-token": UTMFY_API_TOKEN,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending order '{order_id}' to UTMfy with status '{utmify_status}'")
            response = await client.post(UTMFY_API_URL, json=payload, headers=headers)
            if response.status_code not in [200, 201]:
                logger.error(f"UTMfy API Error: {response.status_code} - {response.text}")
            else:
                logger.info("UTMfy order sent successfully.")
        except Exception as e:
            logger.error(f"UTMfy Connection Error: {e}")
