import os
import httpx
import logging
import base64
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BABYLON_BASE_URL = "https://api.bancobabylon.com/functions/v1/transactions"

async def create_pix_payment(
    identifier: str,
    amount: float,
    client_name: str,
    client_email: str,
    client_phone: str,
    client_document: str,
    product_title: str = "Acesso Premium",
    callback_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Creates a Pix payment using Banco Babylon API.
    """
    api_key = os.getenv("BABYLON_API_KEY")

    if not api_key:
        logger.error("Babylon API Key (BABYLON_API_KEY) not found.")
        return None

    # Basic Auth: api_key as username, password empty
    auth_str = f"{api_key}:"
    auth_bytes = auth_str.encode("ascii")
    auth_base64 = base64.b64encode(auth_bytes).decode("ascii")

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json"
    }

    # Babylon expects amount in cents (integer)
    amount_in_cents = int(round(amount * 100))

    # Clean phone (remove non-digits)
    phone_clean = "".join(filter(str.isdigit, client_phone))
    if not phone_clean:
         phone_clean = "11999999999" # Default fallback

    # Clean document (remove non-digits)
    doc_clean = "".join(filter(str.isdigit, client_document))
    doc_type = "CPF" if len(doc_clean) == 11 else "CNPJ"

    payload = {
        "customer": {
            "name": client_name,
            "email": client_email,
            "phone": phone_clean,
            "document": {
                "number": doc_clean,
                "type": doc_type
            }
        },
        "paymentMethod": "PIX",
        "amount": amount_in_cents,
        "items": [
            {
                "title": product_title,
                "unitPrice": amount_in_cents,
                "quantity": 1
            }
        ],
        "pix": {
            "expiresInDays": 1
        },
        "metadata": metadata or {}
    }
    
    # Add identifier to metadata for easier tracking
    payload["metadata"]["identifier"] = identifier

    if callback_url:
        payload["postbackUrl"] = callback_url

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending Pix request to Babylon for ID: {identifier}")
            response = await client.post(BABYLON_BASE_URL, json=payload, headers=headers)
            
            if response.status_code in [200, 201]:
                data = response.json()
                logger.debug(f"Babylon Response: {data}")
                
                # Check for wrapper 'data' or 'result'
                payload = data
                if "data" in data and isinstance(data["data"], dict):
                    payload = data["data"]

                # Extract PIX data with safety
                pix_data = payload.get("pix", {})
                
                # In Babylon, 'qrcode' is actually the PIX Copy/Paste code (starts with 000201)
                # There is no direct image URL in the response
                qr_code = pix_data.get("qrcode") or pix_data.get("qrcodeText") or pix_data.get("brcode")
                qr_image = None # Will regenerate locally in main.py

                if not qr_code:
                     logger.error(f"Missing Pix Code in response. Keys found in pix: {list(pix_data.keys())}")
                     return None

                return {
                    "pix": {
                        "code": qr_code,
                        "image": qr_image
                    }
                }
            else:
                logger.error(f"Babylon API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Babylon Connection Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
