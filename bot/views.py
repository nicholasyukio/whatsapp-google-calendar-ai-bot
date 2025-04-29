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
from bot.lang.database import save_state, load_state, is_context_expired

import bot.lang.database as database

is_local = os.path.exists('.env')

if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

# Configure logging
logger = logging.getLogger(__name__)

# WhatsApp webhook verification token
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN')

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
