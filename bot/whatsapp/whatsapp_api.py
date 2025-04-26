import os
import json
import requests
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# WhatsApp API credentials
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN')

# WhatsApp API endpoints
WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

def send_message(to_phone_number, message_text):
    """
    Send a message to a WhatsApp user using the WhatsApp Business API.
    
    Args:
        to_phone_number (str): The recipient's phone number (with country code)
        message_text (str): The message to send
        
    Returns:
        bool: True if the message was sent successfully, False otherwise
    """
    try:
        # Format the phone number (remove any non-numeric characters)
        formatted_phone = ''.join(filter(str.isdigit, to_phone_number))
        
        # Prepare the request payload
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "text",
            "text": {"body": message_text}
        }
        
        # Set up headers with the access token
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Send the request to the WhatsApp API
        response = requests.post(WHATSAPP_API_URL, json=payload, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            logger.info(f"Message sent successfully to {formatted_phone}")
            return True
        else:
            logger.error(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False

def verify_webhook(token, challenge):
    """
    Verify the webhook for WhatsApp API
    
    Args:
        token (str): The verification token from the request
        challenge (str): The challenge string from the request
        
    Returns:
        str: The challenge string if verification is successful, None otherwise
    """
    if token == WHATSAPP_VERIFY_TOKEN:
        return challenge
    return None

def process_webhook(data):
    """
    Process incoming webhook data from WhatsApp API
    
    Args:
        data (dict): The webhook data
        
    Returns:
        tuple: (phone_number, message_text) or (None, None) if no message
    """
    try:
        # Extract the message from the webhook data
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        
        # Get metadata
        metadata = value.get('metadata', {})
        phone_number_id = metadata.get('phone_number_id', 'unknown')
        
        # Check if this is a status update
        statuses = value.get('statuses', [])
        if statuses:
            status = statuses[0].get('status', 'unknown')
            recipient_id = statuses[0].get('recipient_id', 'unknown')
            
            # Log status update
            logger.info("==================================================")
            logger.info(f"STATUS UPDATE: {status.upper()} for message to {recipient_id}")
            logger.info("==================================================")
            
            return None, None
        
        # Check if this is a message
        messages = value.get('messages', [{}])
        if not messages:
            logger.info("==================================================")
            logger.info(f"WEBHOOK RECEIVED: No message content")
            logger.info("==================================================")
            return None, None
        
        message = messages[0]
        
        # Extract the phone number and message text
        phone_number = message.get('from')
        message_text = message.get('text', {}).get('body', '')
        
        # Log the message
        logger.info("==================================================")
        logger.info(f"NEW MESSAGE FROM: {phone_number}")
        logger.info(f"MESSAGE: {message_text}")
        logger.info("==================================================")
        
        return phone_number, message_text
    except Exception as e:
        logger.error(f"Error processing webhook data: {str(e)}", exc_info=True)
        return None, None 