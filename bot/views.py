import requests
import logging
import json
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from bot.lang.workflow import Bot
from bot.whatsapp.whatsapp_api import *

# Set up logging
logger = logging.getLogger(__name__)

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        # Keep existing GET handling for webhook verification
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
            data = json.loads(request.body)
            
            # Process the webhook data to extract the message
            phone_number, message_text = process_webhook(data)
            
            if not phone_number or not message_text:
                return HttpResponse("No message to process", status=200)
            
            # Log incoming message
            logger.info(f"Processing message from {phone_number}: {message_text}")
            
            # Create and use your Bot instance
            bot = Bot({})  # Initialize with empty state
            response = bot.process_webhook_message(phone_number, message_text)
            
            # Send the response back to WhatsApp
            send_message(phone_number, response)
            logger.info(f"Response sent to {phone_number}")
            
            return HttpResponse("Message processed", status=200)
            
        except Exception as e:
            logger.error(f"Error in WhatsApp webhook: {str(e)}", exc_info=True)
            return HttpResponse("Error processing message", status=500)
    
    logger.warning("Received unsupported request method to WhatsApp webhook")
    return HttpResponse("Method not allowed", status=405)
