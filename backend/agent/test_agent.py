import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env manually with full path
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# Check if key loaded
key = os.getenv("OPENAI_API_KEY")
print(f"API Key found: {'YES - ' + key[:8] + '...' if key else 'NO ❌'}")

from agent.agent import process_message


async def test():
    farmer_id = "test_farmer_1"

    tests = [
        "ನನ್ನ ಬೆಳೆಗೆ ರೋಗ ಬಂದಿದೆ",
        "What is tomato price today?",
        "What government schemes in Maharashtra?",
    ]

    for i, message in enumerate(tests, 1):
        print(f"\nTest {i}: {message}")
        print("-" * 40)
        reply = await process_message(farmer_id, message)
        print(f"KrishiMitra: {reply}")


asyncio.run(test())
