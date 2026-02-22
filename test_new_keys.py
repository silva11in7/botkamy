import asyncio
import os
from dotenv import load_dotenv
from api import babylon

async def test():
    load_dotenv()
    print(f"Testing Babylon API:")
    print(f"API Key: {os.getenv('BABYLON_API_KEY')}")
    
    res = await babylon.create_pix_payment(
        identifier="test_babylon_001",
        amount=1.00,
        client_name="João Teste",
        client_email="teste@pagamento.com",
        client_phone="11912345678",
        client_document="12345678909",
        product_title="Produto Teste Babylon"
    )
    
    if res:
        print("✅ SUCCESS!")
        print(f"Pix Copy/Paste: {res['pix']['code']}")
        print(f"QR Code URL: {res['pix']['image']}")
    else:
        print("❌ FAILED! Check the logs.")

if __name__ == "__main__":
    asyncio.run(test())
