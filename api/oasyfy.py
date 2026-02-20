import os
import httpx
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OASYFY_BASE_URL = "https://app.oasyfy.com/api/v1/gateway/pix/receive"

async def create_pix_payment(
    identifier: str,
    amount: float,
    client_name: str,
    client_email: str,
    client_phone: str,
    client_document: str,
    products: Optional[list] = None,
    callback_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Creates a Pix payment using Oasyfy API.
    """
    public_key = os.getenv("OASYFY_PUBLIC_KEY")
    secret_key = os.getenv("OASYFY_SECRET_KEY")

    if not public_key or not secret_key:
        logger.error("Oasyfy credentials not found in environment variables.")
        return None

    headers = {
        "x-public-key": public_key,
        "x-secret-key": secret_key,
        "Content-Type": "application/json"
    }

    payload = {
        "identifier": identifier,
        "amount": amount,
        "client": {
            "name": client_name,
            "email": client_email,
            "phone": client_phone,
            "document": client_document
        }
    }

    if products:
        payload["products"] = products
    
    if callback_url:
        payload["callbackUrl"] = callback_url

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending Pix request to Oasyfy for identifier: {identifier}")
            logger.info(f"Payload: {payload}") # Debug
            response = await client.post(OASYFY_BASE_URL, json=payload, headers=headers)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Oasyfy API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
