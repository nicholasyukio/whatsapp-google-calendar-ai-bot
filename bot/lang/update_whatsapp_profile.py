# update_whatsapp_profile.py

import requests
import os
is_local = os.path.exists('.env')

if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
BOSS_EMAIL = os.getenv("BOSS_EMAIL")
GRAPH_API_VERSION = 'v22.0'

# 🌐 Base URL for the WhatsApp Business Graph API
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}"


def update_profile_info():
    """
    Updates the name, about text, email, and website of the WhatsApp Business profile.
    """
    url = BASE_URL
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "name": "WGCAIBOT",
        "about": "WhatsApp-Google-Calendar-AI-Bot",
        "email": BOSS_EMAIL,
        "websites": ["https://github.com/nicholasyukio/whatsapp-google-calendar-ai-bot", "https://wgcaibot.nicholasyukio.com.br"]
    }

    response = requests.patch(url, headers=headers, json=data)
    print("🔄 Updating profile information...")
    print("Status:", response.status_code)
    print("Response:", response.json())


def update_profile_picture(image_file: str = "profile.png"):
    """
    Updates the profile picture of the WhatsApp Business account.
    """
    url = f"{BASE_URL}/profile/photo"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(script_dir, image_file)

    if not os.path.exists(image_path):
        print("❌ Image 'profile.png' not found.")
        exit()

    try:
        with open(image_path, "rb") as img:
            files = {
                "file": img,
                "height": (None, "640"),
                "width": (None, "640")
            }
            response = requests.post(url, headers=headers, files=files)
    except FileNotFoundError:
        print(f"❌ Image '{image_path}' not found.")
        return

    print("🖼️ Updating profile picture...")
    print("Status:", response.status_code)
    print("Response:", response.json())


if __name__ == "__main__":
    update_profile_info()
    update_profile_picture("profile2.png")  # Change the file name if needed
