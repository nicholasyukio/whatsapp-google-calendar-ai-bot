from typing import Dict, Any, List, Optional
from langgraph.graph import Graph, StateGraph
from langchain.prompts import ChatPromptTemplate
import logging
from bot.calendar.calendar_actions import (
    check_availability_node,
    create_event_node,
    cancel_event_node,
    list_events_node
)
from bot.trash.my_types import BotState, ActionResponse, model, create_action_prompt, safe_parse_json, VALID_ACTIONS, find_most_similar_action
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Calendar service
SCOPES = ['https://www.googleapis.com/auth/calendar']
def get_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

calendar_service = get_calendar_service()

# Initialize the model
model = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0
)

# Action prompts
THINK_PROMPT = """
You are a helpful assistant that plans a sequence of actions to handle calendar-related requests.
Your job is to analyze the user's input and determine which actions need to be executed.

Available actions:
- check_availability: Check if a time slot is available
- create_event: Create a new calendar event
- cancel_event: Cancel an existing event
- list_events: List events for a specific date
- get_event_details: Get details of a specific event
- notify_participants: Notify event participants
- check_conflicts: Check for scheduling conflicts

Return a response in this format:
{
    "status": "done",
    "info": "action1/action2/action3",
    "next_action": "action1"
}
"""

GEN_RESPONSE_PROMPT = """You are a helpful secretary assistant managing a calendar. Generate a response based on the collected information.

Response types:
1. greeting: For conversation start, include small talk and ask about calendar needs
2. request_done: Confirm completed actions
3. ask_for_info: Request missing information
4. ask_confirmation: Ask for clarification
5. follow_up: Check if more help is needed

Previous actions results:
{action_results}

Generate a response that is:
- Professional but friendly
- Clear and concise
- Helpful and actionable
- In the same language as the user
- Using feminine form if the language allows it

Return a response in this format:
{
    "status": "done",
    "info": "your generated response",
    "next_action": null
}"""

def format_conversation_history(conversation_history):
    """Format the conversation history as a chat transcript for the LLM prompt."""
    formatted = []
    for entry in conversation_history:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role == "user":
            formatted.append(f"User: {content}")
        else:
            formatted.append(f"Assistant: {content}")
    return "\n".join(formatted)

# Action nodes
def think_node(state: BotState) -> Dict[str, Any]:
    """Node that thinks about what to do next."""
    logger.info("==================================================")
    logger.info("THINK NODE INPUT STATE:")
    logger.info(json.dumps(state, indent=2))
    logger.info("==================================================")
    
    # Append the latest user message to conversation_history if not already present
    conversation_history = state.get("conversation_history", [])
    if not conversation_history or conversation_history[-1].get("content") != state["user_input"]:
        conversation_history = conversation_history + [{"role": "user", "content": state["user_input"]}]

    # Format conversation history
    formatted_history = format_conversation_history(conversation_history)

    # Create messages for the LLM
    messages = [
        {"role": "system", "content": "You are a helpful assistant that determines the next action to take based on the conversation."},
        {"role": "human", "content": f"""Given the following conversation, determine what action to take next.\n\nConversation:\n{formatted_history}\n\nAvailable actions:\n{chr(10).join(f"{i+1}. {action} - {description}" for i, (action, description) in enumerate(VALID_ACTIONS.items()))}\n\nRespond with ONLY the action name, nothing else."""}
    ]
    
    # Get the next action from the LLM
    response = model.invoke(messages)
    next_action = response.content.strip().lower()
    
    # Check if the action is valid
    if next_action not in VALID_ACTIONS:
        # Find the most similar valid action
        next_action = find_most_similar_action(next_action)
    
    # Create the result
    result = {
        "current_action": "think",
        "results": {
            "think": {
                "status": "done",
                "info": f"Next action: {next_action}",
                "next_action": next_action
            }
        },
        "next_action": next_action,
        "action_results": state["action_results"] + [
            {
                "status": "done",
                "info": f"Next action: {next_action}",
                "next_action": next_action
            }
        ],
        "conversation_history": conversation_history
    }
    
    logger.info("==================================================")
    logger.info("THINK NODE RESULT:")
    logger.info(json.dumps(result, indent=2))
    logger.info("==================================================")
    
    return result

def gen_response_node(state: BotState) -> Dict[str, Any]:
    """Node that generates a response to the user."""
    logger.info("==================================================")
    logger.info("GEN RESPONSE NODE INPUT STATE:")
    logger.info(json.dumps(state, indent=2))
    logger.info("==================================================")
    
    # Get the user's phone number from the state
    phone_number = state.get("phone_number", "")
    
    # Define boss phone numbers
    BOSS_PHONE_NUMBERS = ["5512981586001"]  # Add the boss's phone number
    
    # Determine user type based on phone number
    user_type = "other"
    if phone_number in BOSS_PHONE_NUMBERS:
        user_type = "boss"
    
    # Define prompts for each user type
    BOSS_RESPONSE_PROMPT = """You are a helpful secretary assistant managing a calendar for your boss.\nGenerate a response based on the collected information.\n\nResponse types:\n1. greeting: For conversation start, include small talk and ask about calendar needs\n2. request_done: Confirm completed actions\n3. ask_for_info: Request missing information\n4. ask_confirmation: Ask for clarification\n5. follow_up: Check if more help is needed\n\nConversation:\n{conversation_history}\n\nPrevious actions results:\n{action_results}\n\nGenerate a response that is:\n- Professional but friendly\n- Clear and concise\n- Helpful and actionable\n- In the same language as the user\n- Using feminine form if the language allows it\n\nReturn a response in this format:\n{{\n    "status": "done",\n    "info": "your generated response",\n    "next_action": null\n}}"""
    
    OTHER_RESPONSE_PROMPT = """You are a helpful secretary assistant managing a calendar. Generate a response based on the collected information.\n\nResponse types:\n1. greeting: For conversation start, include small talk and ask about calendar needs\n2. request_done: Confirm completed actions\n3. ask_for_info: Request missing information\n4. ask_confirmation: Ask for clarification\n5. follow_up: Check if more help is needed\n\nConversation:\n{conversation_history}\n\nPrevious actions results:\n{action_results}\n\nGenerate a response that is:\n- Professional but friendly\n- Clear and concise\n- Helpful and actionable\n- In the same language as the user\n- Using feminine form if the language allows it\n\nReturn a response in this format:\n{{\n    "status": "done",\n    "info": "your generated response",\n    "next_action": null\n}}"""
    
    # Select prompt based on user type
    if user_type == "boss":
        prompt = BOSS_RESPONSE_PROMPT
    else:
        prompt = OTHER_RESPONSE_PROMPT
    
    # Format conversation history
    conversation_history = state.get("conversation_history", [])
    # Append the latest user message if not already present
    if not conversation_history or conversation_history[-1].get("content") != state["user_input"]:
        conversation_history = conversation_history + [{"role": "user", "content": state["user_input"]}]
    formatted_history = format_conversation_history(conversation_history)

    # Format action results
    action_results_str = json.dumps(state["action_results"], indent=2)

    # Create messages for the LLM
    messages = [
        {"role": "system", "content": prompt.format(conversation_history=formatted_history, action_results=action_results_str)},
        {"role": "human", "content": f"Generate a response for the user based on the above conversation and actions."}
    ]
    
    # Get the response from the LLM
    response = model.invoke(messages)
    response_content = response.content.strip()
    
    # Parse the response
    result = safe_parse_json(response_content, ["status", "info", "next_action"])

    # Append the bot's response to conversation_history
    conversation_history = conversation_history + [{"role": "assistant", "content": result.get("info", "") }]

    # Create the return value
    return_value = {
        "current_action": "gen_response",
        "results": {
            "gen_response": result
        },
        "next_action": None,
        "action_results": state["action_results"] + [result],
        "conversation_history": conversation_history
    }
    
    # Log the result
    logger.info("==================================================")
    logger.info("GEN RESPONSE NODE RESULT:")
    logger.info(json.dumps(return_value, indent=2))
    logger.info("==================================================")
    
    return return_value

# Create the graph
def create_workflow() -> Graph:
    workflow = StateGraph(BotState)
    
    # Add nodes
    workflow.add_node("think", think_node)
    workflow.add_node("check_availability", check_availability_node)
    workflow.add_node("create_event", create_event_node)
    workflow.add_node("cancel_event", cancel_event_node)
    workflow.add_node("list_events", list_events_node)
    workflow.add_node("gen_response", gen_response_node)
    
    # Add edges from think to all possible actions
    workflow.add_conditional_edges(
        "think",
        lambda x: x["next_action"],
        {
            "check_availability": "check_availability",
            "create_event": "create_event",
            "cancel_event": "cancel_event",
            "list_events": "list_events",
            "gen_response": "gen_response",
            "respond": "gen_response"
        }
    )
    
    # Add edges from actions to gen_response
    workflow.add_edge("check_availability", "gen_response")
    workflow.add_edge("create_event", "gen_response")
    workflow.add_edge("cancel_event", "gen_response")
    workflow.add_edge("list_events", "gen_response")
    
    # Set entry point
    workflow.set_entry_point("think")
    
    return workflow.compile()

def get_next_action(state: Dict) -> Dict:
    """Determine the next action based on the current state."""
    current_action = state["current_action"]
    next_action = state["next_action"]
    
    if current_action == "think":
        return {"current_action": "act"}
    elif current_action == "act":
        if next_action:
            return {"current_action": next_action}
        else:
            return {"current_action": "respond"}
    elif current_action == "respond":
        return {"current_action": "end"}
    else:
        return {"current_action": "end"}

def think(state: Dict) -> Dict:
    """Think about what action to take based on the user's input."""
    user_input = state["user_input"]
    
    # Create a prompt for the LLM to determine the next action
    prompt = f"""Given the following user message, determine what action to take:
    
User message: {user_input}

Available actions:
1. schedule_meeting - Schedule a meeting in Google Calendar
2. check_availability - Check availability for a specific time
3. list_meetings - List upcoming meetings
4. respond - Send a response to the user

Respond with ONLY the action name, nothing else."""

    # Get the next action from the LLM
    response = model.invoke(prompt)
    next_action = response.strip().lower()
    
    # Update the state with the next action
    state["next_action"] = next_action
    return state 

def act(state: Dict) -> Dict:
    """Perform the action determined by the think function."""
    next_action = state["next_action"]
    user_input = state["user_input"]
    
    if next_action == "schedule_meeting":
        # Extract meeting details from user input
        prompt = f"""Extract meeting details from the following message:
        
User message: {user_input}

Extract and format the following information:
1. Meeting title
2. Date and time
3. Duration (in minutes)
4. Attendees (email addresses)

Format the response as a JSON object with these fields."""
        
        response = model.invoke(prompt)
        meeting_details = json.loads(response)
        
        # Schedule the meeting using Google Calendar API
        try:
            event = calendar_service.events().insert(
                calendarId='primary',
                body={
                    'summary': meeting_details['title'],
                    'start': {
                        'dateTime': meeting_details['date_time'],
                        'timeZone': 'America/Los_Angeles',
                    },
                    'end': {
                        'dateTime': meeting_details['end_time'],
                        'timeZone': 'America/Los_Angeles',
                    },
                    'attendees': [{'email': email} for email in meeting_details['attendees']],
                }
            ).execute()
            
            state["action_result"] = f"Meeting scheduled: {event.get('htmlLink')}"
        except Exception as e:
            state["action_result"] = f"Failed to schedule meeting: {str(e)}"
            
    elif next_action == "check_availability":
        # Extract time from user input
        prompt = f"""Extract the date and time to check availability from:
        
User message: {user_input}

Respond with ONLY the date and time in ISO format (YYYY-MM-DDTHH:MM:SS)."""
        
        date_time = model.invoke(prompt).strip()
        
        # Check availability using Google Calendar API
        try:
            events_result = calendar_service.events().list(
                calendarId='primary',
                timeMin=date_time,
                timeMax=date_time + timedelta(hours=1),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            if not events_result.get('items'):
                state["action_result"] = "The time slot is available."
            else:
                state["action_result"] = "The time slot is not available."
        except Exception as e:
            state["action_result"] = f"Failed to check availability: {str(e)}"
            
    elif next_action == "list_meetings":
        # List upcoming meetings
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            if not events:
                state["action_result"] = "No upcoming meetings found."
            else:
                meetings = []
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    meetings.append(f"{event['summary']} - {start}")
                state["action_result"] = "\n".join(meetings)
        except Exception as e:
            state["action_result"] = f"Failed to list meetings: {str(e)}"
            
    else:
        state["action_result"] = "I'm not sure how to help with that."
    
    return state 