import os
import asyncio
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

async def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ Missing GROQ_API_KEY")
        return

    print(f"Using API Key: {api_key[:10]}...")
    client = AsyncGroq(api_key=api_key)
    
    try:
        # Test common model names
        models = ["llama-3.1-70b-versatile", "llama3-70b-8192", "llama-3.3-70b-versatile"]
        for model in models:
            print(f"\nTesting model: {model}")
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hello, how are you?"}],
                    max_tokens=50
                )
                print(f"✅ MODEL_SUCCESS: {model}")
                print(f"Reply: {response.choices[0].message.content}")
                return # Exit on first success
            except Exception as e:
                print(f"❌ Failed with {model}: {e}")
                
    except Exception as e:
        print(f"❌ Global Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_groq())
