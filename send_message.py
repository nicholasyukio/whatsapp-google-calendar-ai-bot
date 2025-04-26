import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
print(account_sid)

client = Client(account_sid, auth_token)

message = client.messages.create(
    from_='whatsapp:+14155238886',  # Twilio sandbox number
    to='whatsapp:+5512981586001',     # e.g., whatsapp:+5511999998888
    body='Hello from your Django bot via WhatsApp! 🎉'
)

print(f"Message sent! SID: {message.sid}")
