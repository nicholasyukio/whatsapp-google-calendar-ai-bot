# Script to be run only one time to set up Telegram webhook
import requests
import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = "https://yourdomain.com/telegram/webhook"  # Use HTTPS URL

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL})
    
    if response.status_code == 200:
        print("✅ Webhook set successfully!")
        print(response.json())
    else:
        print("❌ Failed to set webhook")
        print(response.status_code, response.text)

if __name__ == "__main__":
    set_webhook()
