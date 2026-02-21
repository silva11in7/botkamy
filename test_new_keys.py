import asyncio
import os
from dotenv import load_dotenv
from api import oasyfy

async def test():
    load_dotenv()
    print(f"Testing keys:")
    print(f"Public: {os.getenv('OASYFY_PUBLIC_KEY')}")
    # print(f"Secret: {os.getenv('OASYFY_SECRET_KEY')}")
    
    res = await oasyfy.create_pix_payment(
        identifier="test_debug_123",
        amount=1.00,
        client_name="Test User",
        client_email="test@example.com",
        client_phone="11999999999",
        client_document="12345678909"
    )
    
    if res:
        print("✅ SUCCESS!")
        print(res)
    else:
        print("❌ FAILED!")

if __name__ == "__main__":
    asyncio.run(test())
