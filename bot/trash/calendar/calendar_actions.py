from typing import Dict, Any
from datetime import datetime, timedelta
import bot.calendar.calendar_utils as calendar_utils
from bot.trash.my_types import BotState, ActionResponse, model, create_action_prompt, safe_parse_json
from langchain.prompts import ChatPromptTemplate
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Action prompts
CHECK_AVAILABILITY_PROMPT = create_action_prompt(
    "check_availability",
    "Check if a time slot is available in the calendar. Extract date and time from user input."
)

CREATE_EVENT_PROMPT = create_action_prompt(
    "create_event",
    "Create a new calendar event. Extract title, date, time, and other details from user input."
)

CANCEL_EVENT_PROMPT = create_action_prompt(
    "cancel_event",
    "Cancel an existing calendar event. Extract event title and date from user input."
)

LIST_EVENTS_PROMPT = create_action_prompt(
    "list_events",
    "List events for a specific date. Extract date from user input."
)

GET_EVENT_DETAILS_PROMPT = create_action_prompt(
    "get_event_details",
    "Get details of a specific event. Extract event title and date from user input."
)

NOTIFY_PARTICIPANTS_PROMPT = create_action_prompt(
    "notify_participants",
    "Notify participants about an event. Extract event details from user input."
)

CHECK_CONFLICTS_PROMPT = create_action_prompt(
    "check_conflicts",
    "Check for scheduling conflicts. Extract date and time from user input."
)

def check_availability_node(state: BotState) -> Dict[str, Any]:
    """Check if a time slot is available."""
    try:
        messages = [
            {"role": "system", "content": CHECK_AVAILABILITY_PROMPT},
            {"role": "human", "content": state["user_input"]}
        ]
        
        response = model.invoke(messages)
        result = safe_parse_json(response.content, ["status", "datetime", "next_action"])
        
        if result["status"] == "done":
            # Parse datetime from result
            event_datetime = datetime.fromisoformat(result["datetime"])
            event_end = event_datetime + timedelta(hours=1)
            
            # Check availability
            is_available = calendar_utils.check_availability(event_datetime, event_end)
            
            if is_available:
                result["info"] = f"Time slot {event_datetime.strftime('%Y-%m-%d %H:%M')} is available."
            else:
                result["info"] = f"Time slot {event_datetime.strftime('%Y-%m-%d %H:%M')} is not available."
        
        return {
            "current_action": "check_availability",
            "results": {"check_availability": result},
            "next_action": result["next_action"],
            "action_results": state["action_results"] + [result]
        }
    except Exception as e:
        error_msg = str(e).replace('\n', ' ').replace('"', '')
        logger.error(f"Error in check_availability: {error_msg}")
        error_result = {
            "status": "impossible",
            "info": "Technical error checking availability",
            "next_action": "gen_response"
        }
        return {
            "current_action": "check_availability",
            "results": {"check_availability": error_result},
            "next_action": "gen_response",
            "action_results": state["action_results"] + [error_result]
        }

def create_event_node(state: BotState) -> Dict[str, Any]:
    """Create a new calendar event."""
    try:
        messages = [
            {"role": "system", "content": CREATE_EVENT_PROMPT},
            {"role": "human", "content": state["user_input"]}
        ]
        
        response = model.invoke(messages)
        result = safe_parse_json(response.content, ["status", "title", "datetime", "next_action"])
        
        if result["status"] == "done":
            # Parse event details from result
            title = result["title"]
            event_datetime = datetime.fromisoformat(result["datetime"])
            event_end = event_datetime + timedelta(hours=1)
            
            # Create event
            event = calendar_utils.create_event(title, event_datetime, event_end)
            result["info"] = f"Event '{title}' has been scheduled for {event_datetime.strftime('%Y-%m-%d %H:%M')}."
        
        return {
            "current_action": "create_event",
            "results": {"create_event": result},
            "next_action": result["next_action"],
            "action_results": state["action_results"] + [result]
        }
    except Exception as e:
        error_msg = str(e).replace('\n', ' ').replace('"', '')
        logger.error(f"Error in create_event: {error_msg}")
        error_result = {
            "status": "impossible",
            "info": "Technical error creating event",
            "next_action": "gen_response"
        }
        return {
            "current_action": "create_event",
            "results": {"create_event": error_result},
            "next_action": "gen_response",
            "action_results": state["action_results"] + [error_result]
        }

def cancel_event_node(state: BotState) -> Dict[str, Any]:
    """Cancel an existing calendar event."""
    try:
        messages = [
            {"role": "system", "content": CANCEL_EVENT_PROMPT},
            {"role": "human", "content": state["user_input"]}
        ]
        
        response = model.invoke(messages)
        result = safe_parse_json(response.content, ["status", "title", "datetime", "next_action"])
        
        if result["status"] == "done":
            # Parse event details from result
            title = result["title"]
            event_datetime = datetime.fromisoformat(result["datetime"])
            
            # Find and cancel event
            events = calendar_utils.list_events(
                time_min=event_datetime.isoformat(),
                time_max=(event_datetime + timedelta(days=1)).isoformat()
            )
            
            event_to_cancel = None
            for event in events:
                if event.get('summary', '').lower() == title.lower():
                    event_to_cancel = event
                    break
            
            if event_to_cancel:
                calendar_utils.cancel_event(event_to_cancel['id'])
                result["info"] = f"Event '{title}' has been cancelled."
            else:
                result["status"] = "impossible"
                result["info"] = f"I couldn't find an event titled '{title}' on {event_datetime.strftime('%Y-%m-%d')}."
        
        return {
            "current_action": "cancel_event",
            "results": {"cancel_event": result},
            "next_action": result["next_action"],
            "action_results": state["action_results"] + [result]
        }
    except Exception as e:
        error_msg = str(e).replace('\n', ' ').replace('"', '')
        logger.error(f"Error in cancel_event: {error_msg}")
        error_result = {
            "status": "impossible",
            "info": "Technical error cancelling event",
            "next_action": "gen_response"
        }
        return {
            "current_action": "cancel_event",
            "results": {"cancel_event": error_result},
            "next_action": "gen_response",
            "action_results": state["action_results"] + [error_result]
        }

def list_events_node(state: BotState) -> Dict[str, Any]:
    """List events for a specific date."""
    try:
        messages = [
            {"role": "system", "content": LIST_EVENTS_PROMPT},
            {"role": "human", "content": state["user_input"]}
        ]
        
        response = model.invoke(messages)
        result = safe_parse_json(response.content, ["status", "datetime", "next_action"])
        
        if result["status"] == "done":
            # Parse date from result
            event_datetime = datetime.fromisoformat(result["datetime"])
            
            # List events
            events = calendar_utils.list_events(
                time_min=event_datetime.isoformat(),
                time_max=(event_datetime + timedelta(days=1)).isoformat()
            )
            
            if events:
                event_list = "\n".join([f"- {event.get('summary')}: {event.get('start', {}).get('dateTime', 'No time')}" for event in events])
                result["info"] = f"Events on {event_datetime.strftime('%Y-%m-%d')}:\n{event_list}"
            else:
                result["info"] = f"No events found for {event_datetime.strftime('%Y-%m-%d')}."
        
        return {
            "current_action": "list_events",
            "results": {"list_events": result},
            "next_action": result["next_action"],
            "action_results": state["action_results"] + [result]
        }
    except Exception as e:
        error_msg = str(e).replace('\n', ' ').replace('"', '')
        logger.error(f"Error in list_events: {error_msg}")
        error_result = {
            "status": "impossible",
            "info": "Technical error listing events",
            "next_action": "gen_response"
        }
        return {
            "current_action": "list_events",
            "results": {"list_events": error_result},
            "next_action": "gen_response",
            "action_results": state["action_results"] + [error_result]
        }

# Add more action nodes as needed... 