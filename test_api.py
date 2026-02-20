import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

OASYFY_BASE_URL = "https://app.oasyfy.com/api/v1/gateway/pix/receive"

async def test_oasyfy():
    public_key = os.getenv("OASYFY_PUBLIC_KEY")
    secret_key = os.getenv("OASYFY_SECRET_KEY")

    headers = {
        "x-public-key": public_key,
        "x-secret-key": secret_key,
        "Content-Type": "application/json"
    }

    payload = {
        "identifier": "test_id_12345",
        "amount": 29.91,
        "client": {
            "name": "Teste Antigravity",
            "email": "teste@email.com",
            "phone": "11999999999",
            "document": "12345678909"
        },
        "products": [{
            "id": "vip_live",
            "name": "VIP VITALICIO + 🔥 LIVES",
            "price": 29.91,
            "quantity": 1
        }]
    }

    async with httpx.AsyncClient() as client:
        print("Enviando requisição de teste...")
        response = await client.post(OASYFY_BASE_URL, json=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_oasyfy())
