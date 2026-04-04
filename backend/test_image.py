import asyncio
from backend.services.whatsapp_service import handle_incoming_message


PHONE = "whatsapp:+911234567890"

# 🔹 OPTION 1: Use local image file (recommended)
LOCAL_IMAGE_PATH = "backend/sample_leaf.jpg"

# 🔹 OPTION 2: Use public image URL (optional)
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/3/3f/Tomato_leaf_blight.jpg"


async def test_with_local_image():
    print("\n🧪 TEST: LOCAL IMAGE\n")

    form_data = {
        "From": PHONE,
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": None,  # not needed for local
        "MediaContentType0": "image/jpeg",
        "local_image_path": LOCAL_IMAGE_PATH,  # custom handling
    }

    res = await handle_incoming_message(form_data)
    print("\n🤖 RESPONSE:\n", res)
    print("\n" + "=" * 60)


async def test_with_url_image():
    print("\n🧪 TEST: URL IMAGE\n")

    form_data = {
        "From": PHONE,
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": IMAGE_URL,
        "MediaContentType0": "image/jpeg",
    }

    res = await handle_incoming_message(form_data)
    print("\n🤖 RESPONSE:\n", res)
    print("\n" + "=" * 60)


async def run():
    print("\n🚀 IMAGE TEST STARTED\n")

    # 🔹 Uncomment ONE of these

    await test_with_local_image()
    # await test_with_url_image()

    print("\n✅ IMAGE TEST COMPLETED\n")


if __name__ == "__main__":
    asyncio.run(run())