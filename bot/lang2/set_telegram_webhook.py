# Script to be run only one time to set up Telegram webhook
import requests
import os
is_local = os.path.exists('.env')
if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

print(TELEGRAM_TOKEN)
WEBHOOK_URL_DEV = "https://5f14-2804-7f0-90c0-f68b-9f19-a7b0-19de-4bb.ngrok-free.app/telegram/"
WEBHOOK_URL_PROD = "https://1pn6fst5ei.execute-api.us-east-1.amazonaws.com/production/telegram/"  # Use HTTPS URL

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL_PROD})
    print("Response:", response.status_code, response.text)
    if response.status_code == 200:
        print("✅ Webhook set successfully!")
        print(response.json())
    else:
        print("❌ Failed to set webhook")
        print(response.status_code, response.text)

if __name__ == "__main__":
    set_webhook()
