import os
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# We will fetch this dynamically from DB in the send_order function
UTMFY_API_URL = "https://api.utmify.com.br/api-credentials/orders"

def format_date(date_val: Any) -> str:
    """Formats a date to YYYY-MM-DD HH:MM:SS."""
    if not date_val:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    if isinstance(date_val, str):
        try:
            # Handle ISO format from Supabase (e.g., 2024-07-26T14:35:13.123+00:00 or 2024-07-26T14:35:13Z)
            # Remove Z at the end and other ISO artifacts
            clean_date = date_val.strip().replace('Z', '').replace('T', ' ').split('.')[0].split('+')[0]
            # Try to parse to ensure it's valid
            dt = datetime.strptime(clean_date, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            # Fallback to current time if parsing fails, but logger warn it
            logger.warning(f"Failed to parse date: {date_val}. Using current time.")
            return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    if isinstance(date_val, datetime):
        return date_val.strftime('%Y-%m-%d %H:%M:%S')
        
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

async def send_order(
    order_id: str,
    status: str,
    user_data: Dict[str, Any],
    product_data: Dict[str, Any],
    tracking_data: Optional[Dict[str, Any]] = None,
    transaction_data: Optional[Dict[str, Any]] = None,
    payment_method: str = "pix",
    approved_date: Optional[str] = None
):
    """
    Sends order information to UTMfy Orders API.
    """
    # Fetch token dynamically from database
    token = database.get_setting("utmfy_api_token") or os.getenv("UTMFY_API_TOKEN")
    
    if not token:
        logger.warning("UTMFY_API_TOKEN not configured in DB or ENV. Skipping event.")
        return

    # Map status
    status_map = {
        "waiting": "waiting_payment",
        "pending": "waiting_payment",
        "waiting_payment": "waiting_payment",
        "paid": "paid",
        "confirmed": "paid",
        "refused": "refused",
        "refunded": "refunded",
        "chargedback": "chargedback"
    }
    utmify_status = status_map.get(status.lower(), "waiting_payment")

    # Use transaction created_at if available, else user created_at, else now
    raw_created_at = None
    if transaction_data and transaction_data.get("created_at"):
        raw_created_at = transaction_data.get("created_at")
    elif user_data and user_data.get("created_at"):
        raw_created_at = user_data.get("created_at")
    
    created_at = format_date(raw_created_at)
    
    # Format approved_date if present
    formatted_approved = None
    if approved_date:
        formatted_approved = format_date(approved_date)
    elif utmify_status == "paid":
        formatted_approved = format_date(None) # Now

    payload = {
        "orderId": order_id,
        "platform": "KamyBot",
        "paymentMethod": payment_method,
        "status": utmify_status,
        "createdAt": created_at,
        "approvedDate": formatted_approved,
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
                "id": str(product_data.get("id", "vip")),
                "name": product_data.get("name", "Acesso VIP"),
                "planId": None,
                "planName": None,
                "quantity": 1,
                "priceInCents": int(round(float(product_data.get("price", 0)) * 100))
            }
        ],
        "trackingParameters": {
            "src": tracking_data.get("src") if tracking_data else None,
            "sck": tracking_data.get("sck") if tracking_data else None,
            "utm_source": tracking_data.get("utm_source") if tracking_data else None,
            "utm_medium": tracking_data.get("utm_medium") if tracking_data else None,
            "utm_campaign": tracking_data.get("utm_campaign") if tracking_data else None,
            "utm_content": tracking_data.get("utm_content") if tracking_data else None,
            "utm_term": tracking_data.get("utm_term") if tracking_data else None
        },
        "commission": {
            "totalPriceInCents": int(round(float(product_data.get("price", 0)) * 100)),
            "gatewayFeeInCents": 0,
            "userCommissionInCents": int(round(float(product_data.get("price", 0)) * 100))
        },
        "isTest": False
    }

    # Add IP if present
    if user_data.get("ip"):
        payload["customer"]["ip"] = user_data["ip"]

    headers = {
        "x-api-token": token,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"UTMfy Request: {utmify_status} for {order_id}")
            response = await client.post(UTMFY_API_URL, json=payload, headers=headers)
            if response.status_code not in [200, 201]:
                logger.error(f"UTMfy API Error: {response.status_code} - {response.text}")
            else:
                logger.info(f"UTMfy Successfully Sent: {utmify_status}")
        except Exception as e:
            logger.error(f"UTMfy Connection Error: {e}")
