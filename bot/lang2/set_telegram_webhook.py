# Script to be run only one time to set up Telegram webhook
import requests
import os
is_local = os.path.exists('.env')
if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
print(TELEGRAM_TOKEN)
WEBHOOK_URL = "https://1pn6fst5ei.execute-api.us-east-1.amazonaws.com/production/telegram/"  # Use HTTPS URL

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL})
    print("Response:", response.status_code, response.text)
    if response.status_code == 200:
        print("✅ Webhook set successfully!")
        print(response.json())
    else:
        print("❌ Failed to set webhook")
        print(response.status_code, response.text)

if __name__ == "__main__":
    set_webhook()
