import httpx
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AMPLOPAY_BASE_URL = "https://app.amplopay.com/api/v1/gateway/pix/receive"


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
    Creates a Pix payment using AmploPay API.
    Returns standardized format: {"pix": {"code": ..., "image": ...}}
    """
    if not credentials:
        logger.error("AmploPay credentials not provided.")
        return None

    public_key = credentials.get("public_key")
    secret_key = credentials.get("secret_key")

    if not public_key or not secret_key:
        logger.error("AmploPay public_key or secret_key missing from credentials.")
        return None

    headers = {
        "x-public-key": public_key,
        "x-secret-key": secret_key,
        "Content-Type": "application/json"
    }

    # Clean phone (remove non-digits)
    phone_clean = "".join(filter(str.isdigit, client_phone))
    if not phone_clean:
        phone_clean = "11999999999"

    # Clean document (remove non-digits)
    doc_clean = "".join(filter(str.isdigit, client_document))

    payload = {
        "identifier": identifier,
        "amount": amount,
        "client": {
            "name": client_name,
            "email": client_email,
            "phone": phone_clean,
            "document": doc_clean
        },
        "metadata": metadata or {}
    }

    # Add identifier to metadata for tracking
    payload["metadata"]["identifier"] = identifier

    if callback_url:
        payload["callbackUrl"] = callback_url

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending Pix request to AmploPay for ID: {identifier}")
            response = await client.post(AMPLOPAY_BASE_URL, json=payload, headers=headers)

            if response.status_code in [200, 201]:
                data = response.json()
                logger.debug(f"AmploPay Response: {data}")

                pix_data = data.get("pix", {})
                pix_code = pix_data.get("code")
                pix_image = pix_data.get("image")
                pix_base64 = pix_data.get("base64")

                if not pix_code:
                    logger.error(f"Missing Pix Code in AmploPay response. Keys: {list(data.keys())}")
                    return None

                return {
                    "pix": {
                        "code": pix_code,
                        "image": pix_image,
                        "base64": pix_base64
                    }
                }
            else:
                logger.error(f"AmploPay API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"AmploPay Connection Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
