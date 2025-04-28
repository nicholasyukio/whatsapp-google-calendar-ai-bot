import requests
import logging
import json
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from bot.trash.langchain_utils import *
from bot.whatsapp.whatsapp_api import *
from bot.trash.langgraph_utils import create_workflow, BotState

# Set up logging
logger = logging.getLogger(__name__)

@csrf_exempt  # WhatsApp API doesn't send CSRF tokens
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
            data = json.loads(request.body)
            
            # Process the webhook data to extract the message
            phone_number, message_text = process_webhook(data)
            
            if not phone_number or not message_text:
                # This is a status update or other webhook without a message
                return HttpResponse("No message to process", status=200)
            
            # Log incoming message
            logger.info(f"Processing message from {phone_number}: {message_text}")
            
            # Create initial state
            initial_state = {
                "messages": [],
                "current_action": "think",
                "results": {},
                "next_action": None,
                "user_input": message_text,
                "phone_number": phone_number,
                "action_results": []
            }
            
            # Create and run the workflow
            workflow = create_workflow()
            final_state = workflow.invoke(initial_state)
            
            # Get the final response
            try:
                # First try the expected structure
                if "results" in final_state and "gen_response" in final_state["results"]:
                    final_response = final_state["results"]["gen_response"]["info"]
                # If that fails, try to get the last action result
                elif "action_results" in final_state and final_state["action_results"]:
                    # Get the last action result
                    last_result = final_state["action_results"][-1]
                    final_response = last_result["info"]
                else:
                    # If all else fails, use a default response
                    final_response = "I'm sorry, I encountered an error processing your request."
                
                logger.info(f"Generated response: {final_response}")
            except Exception as e:
                logger.error(f"Error accessing final response: {str(e)}")
                final_response = "I'm sorry, I encountered an error processing your request."
            
            # Send the response back to WhatsApp
            send_message(phone_number, final_response)
            logger.info(f"Response sent to {phone_number}")
            
            return HttpResponse("Message processed", status=200)
        except Exception as e:
            logger.error(f"Error in WhatsApp webhook: {str(e)}", exc_info=True)
            return HttpResponse("Error processing message", status=500)
    
    logger.warning("Received unsupported request method to WhatsApp webhook")
    return HttpResponse("Method not allowed", status=405)

def get_available_slots(request):
    # Define the query to fetch available slots from the database
    query = "SELECT * FROM bot_meetingslot WHERE status = 'available'"

    # Use the cursor to execute the query
    with connection.cursor() as cursor:
        cursor.execute(query)
        available_slots = cursor.fetchall()

    # Process the available slots into a more readable format (list of dicts)
    slots = []
    for slot in available_slots:
        slot_data = {
            'id': slot[0],  # assuming the first column is 'id'
            'start_time': slot[1],  # assuming the second column is 'start_time'
            'end_time': slot[2],  # assuming the third column is 'end_time'
            'status': slot[3],  # assuming the fourth column is 'status'
        }
        slots.append(slot_data)

    # Return the available slots as a JSON response
    return JsonResponse(slots, safe=False)
