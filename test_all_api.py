import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

OASYFY_BASE_URL = "https://app.oasyfy.com/api/v1/gateway/pix/receive"

PRODUCTS = {
    "vip_live": {"name": "VIP VITALICIO + 🔥 LIVES", "price": 29.91, "desc": "Acesso vitalício + Lives exclusivas"},
    "vip_vital": {"name": "VIP VITALICIO 💎", "price": 21.91, "desc": "Acesso vitalício a todo conteúdo"},
    "vip_mensal": {"name": "VIP MENSAL 😈", "price": 17.91, "desc": "Acesso por 30 dias"},
    "vip_live_disc": {"name": "VIP VITALICIO + 🔥 LIVES (15% OFF)", "price": 25.41, "desc": "Acesso vitalício + Lives exclusivas"},
    "vip_vital_disc": {"name": "VIP VITALICIO 💎 (15% OFF)", "price": 18.91, "desc": "Acesso vitalício a todo conteúdo"},
    "vip_mensal_disc": {"name": "VIP MENSAL 😈 (15% OFF)", "price": 15.37, "desc": "Acesso por 30 dias"},
    "vip_live_disc2": {"name": "VIP VITALICIO + 🔥 LIVES (20% OFF)", "price": 21.90, "desc": "Acesso vitalício + Lives exclusivas"},
    "vip_vital_disc2": {"name": "VIP VITALICIO 🔥 (20% OFF)", "price": 16.62, "desc": "Acesso vitalício a todo conteúdo"},
    "vip_mensal_disc2": {"name": "VIP MENSAL 🔥 (20% OFF)", "price": 13.28, "desc": "Acesso por 30 dias"}
}

async def test_all_products():
    public_key = os.getenv("OASYFY_PUBLIC_KEY")
    secret_key = os.getenv("OASYFY_SECRET_KEY")

    headers = {
        "x-public-key": public_key,
        "x-secret-key": secret_key,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        for product_id, product in PRODUCTS.items():
            payload = {
                "identifier": f"test_{product_id}",
                "amount": product['price'],
                "client": {
                    "name": "Teste " + product_id,
                    "email": "teste@email.com",
                    "phone": "11999999999",
                    "document": "12345678909"
                },
                "products": [{
                    "id": product_id,
                    "name": product['name'],
                    "price": product['price'],
                    "quantity": 1
                }]
            }

            print(f"Testando: {product_id}...")
            try:
                response = await client.post(OASYFY_BASE_URL, json=payload, headers=headers)
                if response.status_code in [200, 201]:
                    print(f"  [OK] - Status: {response.status_code}")
                else:
                    print(f"  [FAIL] - Status: {response.status_code}")
                    print(f"  Response: {response.text}")
            except Exception as e:
                print(f"  [ERROR]: {e}")

if __name__ == "__main__":
    asyncio.run(test_all_products())
