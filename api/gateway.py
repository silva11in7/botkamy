import os
import logging
from typing import Optional, Dict, Any
import database
from api import babylon, oasyfy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_payment(
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
    Gateway dispatcher: reads the active gateway from DB and routes
    to the correct provider module.
    Returns standardized format: {"pix": {"code": ..., "image": ...}}
    """
    gw = database.get_active_gateway()

    if not gw:
        logger.error("No active gateway configured! Cannot process payment.")
        return None

    provider = gw.get("provider", "").lower()
    credentials = gw.get("credentials", {})
    gw_name = gw.get("name", provider)

    logger.info(f"Processing payment via [{gw_name}] (provider: {provider})")

    if provider == "babylon":
        # Babylon uses env vars for auth (legacy), but we can also pass from credentials
        # Set env var temporarily if credentials have api_key
        if credentials.get("api_key"):
            os.environ["BABYLON_API_KEY"] = credentials["api_key"]

        return await babylon.create_pix_payment(
            identifier=identifier,
            amount=amount,
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            client_document=client_document,
            product_title=product_title,
            callback_url=callback_url,
            metadata=metadata
        )

    elif provider == "oasyfy":
        return await oasyfy.create_pix_payment(
            identifier=identifier,
            amount=amount,
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            client_document=client_document,
            product_title=product_title,
            callback_url=callback_url,
            metadata=metadata,
            credentials=credentials
        )

    else:
        logger.error(f"Unknown gateway provider: {provider}")
        return None
