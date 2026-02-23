import httpx
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GENESYS_BASE_URL = "https://api.genesys.finance/v1/transactions"


async def create_pix_payment(
    identifier: str,
    amount: float,
    client_name: str,
    client_email: str,
    client_phone: str,
    client_document: str,
    product_title: str = "Acesso Premium",
    callback_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    credentials: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Creates a Pix payment using Genesys Finance API.
    Returns standardized format: {"pix": {"code": ..., "image": ...}}
    """
    if not credentials:
        logger.error("Genesys credentials not provided.")
        return None

    api_secret = credentials.get("api_secret")
    if not api_secret:
        logger.error("Genesys api_secret missing from credentials.")
        return None

    headers = {
        "api-secret": api_secret,
        "Content-Type": "application/json"
    }

    # Clean phone (remove non-digits)
    phone_clean = "".join(filter(str.isdigit, client_phone))
    if not phone_clean:
        phone_clean = "11999999999"

    # Clean document (remove non-digits)
    doc_clean = "".join(filter(str.isdigit, client_document))
    doc_type = "CPF" if len(doc_clean) <= 11 else "CNPJ"

    payload = {
        "external_id": identifier,
        "total_amount": amount,
        "payment_method": "PIX",
        "items": [
            {
                "id": identifier,
                "title": product_title,
                "description": product_title,
                "price": amount,
                "quantity": 1,
                "is_physical": False
            }
        ],
        "customer": {
            "name": client_name,
            "email": client_email,
            "phone": phone_clean,
            "document_type": doc_type,
            "document": doc_clean
        }
    }

    if callback_url and callback_url.startswith("http"):
        payload["webhook_url"] = callback_url

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending Pix request to Genesys for ID: {identifier}")
            response = await client.post(GENESYS_BASE_URL, json=payload, headers=headers)

            if response.status_code in [200, 201]:
                data = response.json()
                logger.debug(f"Genesys Response: {data}")

                if data.get("hasError"):
                    logger.error(f"Genesys returned error: {data}")
                    return None

                pix_data = data.get("pix", {})
                # Genesys uses "payload" instead of "code"
                pix_code = pix_data.get("payload") or pix_data.get("code")

                if not pix_code:
                    logger.error(f"Missing Pix Code in Genesys response. Keys: {list(data.keys())}")
                    return None

                return {
                    "pix": {
                        "code": pix_code,
                        "image": None  # Genesys doesn't return QR image, generated locally
                    }
                }
            else:
                logger.error(f"Genesys API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Genesys Connection Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
