import os
import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv
import sys
import os
import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.whatsapp.whatsapp_api import send_message
#from bot.calendar.calendar_service import CalendarService

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# WhatsApp webhook verification token
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN')
print(WHATSAPP_VERIFY_TOKEN)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    """
    Handle incoming webhook requests from WhatsApp.
    
    For GET requests: Verify the webhook
    For POST requests: Process incoming messages
    """
    if request.method == "GET":
        return verify_webhook(request)
    else:
        return process_message(request)

def verify_webhook(request):
    """
    Verify the webhook with WhatsApp.
    
    Args:
        request: The HTTP request object
        
    Returns:
        HttpResponse: The verification response
    """
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return HttpResponse(challenge, status=200)
        else:
            logger.error("Webhook verification failed")
            return HttpResponse("Forbidden", status=403)
    
    return HttpResponse("Bad Request", status=400)

def process_message(request):
    """
    Process incoming messages from WhatsApp.
    
    Args:
        request: The HTTP request object
        
    Returns:
        HttpResponse: The response to WhatsApp
    """
    try:
        # Parse the request body
        body = json.loads(request.body)
        
        # Check if this is a WhatsApp message event
        if body.get("object") == "whatsapp_business_account":
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("value", {}).get("messages"):
                        for message in change["value"]["messages"]:
                            # Extract message details
                            from_number = message.get("from")
                            message_text = message.get("text", {}).get("body", "")
                            
                            # Print the phone number to the terminal
                            print(f"\n{'='*50}")
                            print(f"📱 RECEIVED MESSAGE FROM: {from_number}")
                            print(f"💬 MESSAGE: {message_text}")
                            print(f"{'='*50}\n")
                            
                            # Process the message and get a response
                            response_text = handle_message(message_text)
                            
                            # Print the response to the terminal
                            print(f"\n{'='*50}")
                            print(f"📤 SENDING RESPONSE TO: {from_number}")
                            print(f"💬 RESPONSE: {response_text}")
                            print(f"{'='*50}\n")
                            
                            # Send the response back to the user
                            if response_text:
                                send_message(from_number, response_text)
            
            return HttpResponse("OK", status=200)
        else:
            return HttpResponse("Not a WhatsApp message", status=400)
            
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse("Internal Server Error", status=500)

def handle_message(message_text):
    """
    Process the incoming message and generate a response.
    
    Args:
        message_text (str): The incoming message text
        
    Returns:
        str: The response message
    """
    # Initialize the calendar service
    calendar_service = CalendarService()
    
    # Process the message based on its content
    # This is a simple example - you can expand this based on your needs
    if "schedule" in message_text.lower():
        # Handle scheduling requests
        try:
            # Extract event details from the message
            # This is a simplified example - you might want to use NLP or a more sophisticated parser
            event_details = parse_event_details(message_text)
            
            # Create the event
            event = calendar_service.create_event(
                summary=event_details["summary"],
                start_time=event_details["start_time"],
                end_time=event_details["end_time"],
                description=event_details.get("description", ""),
                location=event_details.get("location", "")
            )
            
            return f"Event scheduled successfully!\nTitle: {event['summary']}\nStart: {event['start']}\nEnd: {event['end']}"
            
        except Exception as e:
            logger.error(f"Error scheduling event: {str(e)}")
            return "Sorry, I couldn't schedule the event. Please try again with a different format."
            
    elif "list" in message_text.lower() and "events" in message_text.lower():
        # Handle event listing requests
        try:
            # Check if the user wants past events
            include_past = False
            if "past" in message_text.lower() or "history" in message_text.lower() or "last" in message_text.lower():
                include_past = True
                logger.info("Including past events in the response")
            
            # Get the events
            events = calendar_service.list_events(include_past=include_past)
            
            if events and len(events) > 0:
                # Determine the time range for the response message
                time_range = "upcoming" if not include_past else "past and upcoming"
                
                response = f"Here are your {time_range} events:\n\n"
                for event in events:
                    # Extract start and end times
                    start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'No time'))
                    end = event.get('end', {}).get('dateTime', event.get('end', {}).get('date', 'No time'))
                    
                    # Format the times for better readability
                    try:
                        start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                        start_formatted = start_dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        start_formatted = start
                        
                    try:
                        end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
                        end_formatted = end_dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        end_formatted = end
                    
                    response += f"- {event.get('summary', 'Untitled')} ({start_formatted} to {end_formatted})\n"
                return response
            else:
                time_range = "upcoming" if not include_past else "past or upcoming"
                return f"You don't have any {time_range} events."
                
        except Exception as e:
            logger.error(f"Error listing events: {str(e)}")
            return "Sorry, I couldn't retrieve your events. Please try again later."
            
    else:
        return "I can help you schedule events or list your upcoming events. Just let me know what you'd like to do!"

def parse_event_details(message_text):
    """
    Parse event details from a message.
    
    Args:
        message_text (str): The message containing event details
        
    Returns:
        dict: The parsed event details
    """
    # This is a simplified example - you might want to use NLP or a more sophisticated parser
    # For now, we'll just return some dummy data
    return {
        "summary": "Sample Event",
        "start_time": "2024-03-20T10:00:00",
        "end_time": "2024-03-20T11:00:00",
        "description": "This is a sample event",
        "location": "Sample Location"
    } 