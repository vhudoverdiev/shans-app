import os
import uuid
import requests


VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN")
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")


def send_vk_message(user_id: int, text: str):
    if not VK_GROUP_TOKEN:
        return False, "VK_GROUP_TOKEN не задан в .env"

    url = "https://api.vk.com/method/messages.send"

    payload = {
        "user_id": user_id,
        "random_id": int(uuid.uuid4().int % 2_000_000_000),
        "message": text,
        "access_token": VK_GROUP_TOKEN,
        "v": VK_API_VERSION,
    }

    try:
        response = requests.post(url, data=payload, timeout=15)
        data = response.json()

        if "error" in data:
            return False, data["error"].get("error_msg", "Ошибка VK API")

        return True, "ok"
    except Exception as exc:
        return False, str(exc)
