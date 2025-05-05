import requests
import logging
import json
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import os
import datetime
from bot.whatsapp.whatsapp_api import *
from bot.lang.workflow import Bot
from bot.lang2.workflow2 import Bot2
import bot.lang.database as database

is_local = os.path.exists('.env')

if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

# Configure logging
logger = logging.getLogger(__name__)

# WhatsApp webhook verification token
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def download_voice(file_id: str, dest_path: str = "/tmp/audio.ogg") -> str:
    """
    Downloads the voice file from Telegram and saves it locally.

    Args:
        file_id: The Telegram file_id of the voice message.
        dest_path: Local path to save the audio file.

    Returns:
        The local path to the downloaded file.
    """
    # Step 1: Get file path from Telegram API
    file_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}"
    response = requests.get(file_info_url)
    response.raise_for_status()
    file_path = response.json()["result"]["file_path"]

    # Step 2: Download the actual file
    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    audio_data = requests.get(download_url)
    audio_data.raise_for_status()

    # Step 3: Save to /tmp (or another path)
    with open(dest_path, "wb") as f:
        f.write(audio_data.content)

    return dest_path

def transcribe_audio_file(file_path: str) -> str:
    """
    Sends a local audio file to Deepgram for transcription.

    Args:
        file_path: Path to the OGG audio file (downloaded from Telegram).
        deepgram_api_key: Your Deepgram API key.

    Returns:
        The transcribed text or an error message.
    """
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/ogg"
    }

    params = {
        "model": "nova-2",
        "smart_format": "true"
    }

    try:
        with open(file_path, "rb") as audio:
            response = requests.post(
                "https://api.deepgram.com/v1/listen",
                headers=headers,
                params=params,
                data=audio
            )
        response.raise_for_status()
        transcript = response.json()
        return transcript["results"]["channels"][0]["alternatives"][0]["transcript"]
    except Exception as e:
        return f"Error during transcription: {e}"

@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        if "message" in data:
            # user_id = data["message"]["chat"]["id"]
            # user_id_str = str(user_id)
            # user_msg = data["message"].get("text", "")
            # bot2 = Bot2()
            # response = bot2.process_webhook_message(user_id_str, user_msg)
            # send_message(user_id, response)
            message = data["message"]
            user_id = message["chat"]["id"]
            user_id_str = str(user_id)

            # If it's voice
            if "voice" in message:
                file_id = message["voice"]["file_id"]
                file_path = download_voice(file_id)
                transcription = transcribe_audio_file(file_path)

                # Pass transcribed text to your bot logic
                bot2 = Bot2()
                response = bot2.process_webhook_message(user_id_str, transcription)
                send_message(user_id, response)

            # Fallback to regular text
            elif "text" in message:
                user_msg = message["text"]
                bot2 = Bot2()
                response = bot2.process_webhook_message(user_id_str, user_msg)
                send_message(user_id, response)
    except Exception as e:
        print(f"Error processing webhook: {e}")
    return JsonResponse({"status": "ok"})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        # Handle webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode and token:
            if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
                logger.info("WhatsApp webhook verified successfully")
                return HttpResponse(challenge, content_type='text/plain')
            else:
                logger.warning("WhatsApp webhook verification failed")
                return HttpResponse("Verification failed", status=403)
    
    elif request.method == "POST":
        try:
            # Parse the incoming webhook data
            body = json.loads(request.body)
            
            # Check if this is a WhatsApp message event
            if body.get("object") == "whatsapp_business_account":
                for entry in body.get("entry", []):
                    for change in entry.get("changes", []):
                        if change.get("value", {}).get("messages"):
                            for message in change["value"]["messages"]:
                                # Extract message details
                                phone_number = message.get("from")
                                message_text = message.get("text", {}).get("body", "")
                                message_id = message.get("id")

                                is_message_new = database.register_message_id(message_id)

                                if is_message_new:
                                
                                    # Log incoming message
                                    logger.info(f"Processing message from {phone_number}: {message_text}")
                                    print(f"\n{'='*50}")
                                    print(f"📱 RECEIVED MESSAGE FROM: {phone_number}")
                                    print(f"💬 MESSAGE: {message_text}")
                                    print(f"{'='*50}\n")
                                    
                                    if not phone_number or not message_text:
                                        continue
                                    
                                    # Create and use your Bot instance
                                    bot = Bot({})  # Initialize with empty state
                                    response = bot.process_webhook_message(phone_number, message_text)
                                    
                                    # Log outgoing message
                                    logger.info(f"Response sent to {phone_number}")
                                    print(f"\n{'='*50}")
                                    print(f"📤 SENDING RESPONSE TO: {phone_number}")
                                    print(f"💬 RESPONSE: {response}")
                                    print(f"{'='*50}\n")
                                    
                                    # Send the response back to WhatsApp
                                    send_message(phone_number, response)
                
                return HttpResponse("OK", status=200)
            else:
                logger.warning("Not a WhatsApp message")
                return HttpResponse("Not a WhatsApp message", status=400)
            
        except Exception as e:
            logger.error(f"Error in WhatsApp webhook: {str(e)}", exc_info=True)
            return HttpResponse("Error processing message", status=500)
    
    logger.warning("Received unsupported request method to WhatsApp webhook")
    return HttpResponse("Method not allowed", status=405)

def home(request):
    """
    Simple home view that returns a welcome message and status information.
    Useful for verifying deployment and as a health check endpoint.
    """
    return JsonResponse({
        'status': 'ok',
        'message': 'WhatsApp Calendar Bot API is running',
        'version': '1.0.0',
        'endpoints': {
            'webhook': '/whatsapp/',
        }
    })
