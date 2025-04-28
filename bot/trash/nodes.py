from typing import Dict, Any
from datetime import datetime
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from bot.trash.my_types import (
    BotState, ActionResult, ThinkingResult, model, MAX_ITERATIONS, 
    safe_parse_json, create_initial_state
)
import bot.calendar.calendar_utils as calendar_utils
import json

THINKING_PROMPT = """You are an AI assistant managing a calendar through WhatsApp. Analyze the current state and decide what action is needed next.

Current state:
{state}

Your task is to:
1. Analyze what information we have
2. Determine what information is still needed
3. Suggest the next action to take
4. Provide reasoning for your decision

Available actions:
- check_availability: Check if a time slot is free
- create_event: Create a new calendar event
- cancel_event: Cancel an existing event
- list_events: List events for a date
- gen_response: Generate final response to user

You cannot suggest actions not in this list.

Return your response in this JSON format:
{
    "required_info": ["list", "of", "missing", "information"],
    "suggested_action": "one_of_the_available_actions",
    "reasoning": "your reasoning for this decision"
}"""

def thinking_node(state: BotState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze state and decide next action."""
    messages = [
        SystemMessage(content=THINKING_PROMPT),
        HumanMessage(content=json.dumps(state, indent=2))
    ]
    
    response = model.invoke(messages)
    result = safe_parse_json(response.content, ["required_info", "suggested_action", "reasoning"])
    
    # Create a proper ThinkingResult
    thinking_result: ThinkingResult = {
        "required_info": result["required_info"],
        "suggested_action": result["suggested_action"],
        "reasoning": result["reasoning"]
    }
    
    # Update state
    state["thinking_results"].append(thinking_result)
    state["iteration_count"] += 1
    
    return {"state": state}

def check_availability_node(state: BotState, config: RunnableConfig) -> Dict[str, Any]:
    """Check calendar availability."""
    try:
        # Extract datetime from thinking results or user input
        # Implementation here
        
        result: ActionResult = {
            "action": "check_availability",
            "status": "success",
            "data": {
                "is_available": True,  # Replace with actual check
                "datetime": "2024-03-20T10:00:00"  # Replace with actual datetime
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        result: ActionResult = {
            "action": "check_availability",
            "status": "failure",
            "data": {"error": str(e)},
            "timestamp": datetime.now().isoformat()
        }
    
    state["action_results"].append(result)
    return {"state": state}

def create_event_node(state: BotState, config: RunnableConfig) -> Dict[str, Any]:
    """Create a calendar event."""
    try:
        # Extract event details from thinking results
        # Implementation here
        
        result: ActionResult = {
            "action": "create_event",
            "status": "success",
            "data": {
                "event_id": "123",  # Replace with actual event ID
                "title": "Meeting",  # Replace with actual title
                "datetime": "2024-03-20T10:00:00"  # Replace with actual datetime
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        result: ActionResult = {
            "action": "create_event",
            "status": "failure",
            "data": {"error": str(e)},
            "timestamp": datetime.now().isoformat()
        }
    
    state["action_results"].append(result)
    return {"state": state}

def gen_response_node(state: BotState, config: RunnableConfig) -> Dict[str, Any]:
    """Generate final response based on accumulated state."""
    messages = [
        SystemMessage(content="Generate a natural response to the user based on all actions taken."),
        HumanMessage(content=json.dumps(state, indent=2))
    ]
    
    response = model.invoke(messages)
    state["final_response"] = response.content
    
    return {"state": state}

def router(state: BotState, config: RunnableConfig) -> Dict[str, Any]:
    """Route to next action based on thinking results."""
    # Force response generation if max iterations reached
    if state["iteration_count"] >= MAX_ITERATIONS:
        return {"next": "gen_response"}
    
    # Get latest thinking result
    if not state["thinking_results"]:
        return {"next": "thinking"}
    
    latest_thinking = state["thinking_results"][-1]
    next_action = latest_thinking["suggested_action"]
    
    # Validate action exists
    valid_actions = ["thinking", "check_availability", "create_event", "cancel_event", "list_events", "gen_response"]
    if next_action not in valid_actions:
        return {"next": "gen_response"}
    
    return {"next": next_action} 