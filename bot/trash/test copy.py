from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from typing import TypedDict, List, Literal
import new_langchain_utils
from datetime import datetime
import math
import google_calendar
import numpy as np
import prompts

BOSS_NAME = "Nicholas"

class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

class ActionInput(TypedDict, total=False):  # total=False makes all fields optional
    event_name: str
    start_time: str
    end_time: str
    description: str
    invited_people: List[str]
    location: str

class ActionResult(TypedDict, total=False):
    success: bool
    info: str

# ----- Define BotState -----
class BotState(TypedDict):
    input_msg: str
    context: List[ChatMessage]
    is_boss: bool
    greeted: bool
    user_id: str
    username: str
    user_intent: Literal["schedule", "list", "cancel", "check", "update", "none"]
    chosen_action: Literal["greet", "take_intent", "request_more_info", "follow_up"]
    action_input: ActionInput
    action_result: ActionResult
    response: str

# ----- Simulated Calendar -----
calendar_events = []

# ----- Nodes -----

# Define the main Bot class
class Bot:
    def __init__(self, state: BotState):
        self.state = state
        self.user = self.User(state)
        self.action_handler = self.ActionHandler(state)

    def identify_user(self) -> None:
        user_id = self.state["user_id"]
        is_boss = self.state["is_boss"]
        username = self.state["username"]
        
        if self.state["user_id"] == "":
            user_id = "boss" if BOSS_NAME in self.state["input_msg"] else "other"
            is_boss = user_id == "boss"
            username_result = new_langchain_utils.identify_user(self.state["input_msg"])
            username = username_result["username"]
            print("# user_id: ", user_id)
            print("# is_boss: ", is_boss)
            print("# username: ", username)

        self.state.update({"user_id": user_id, "is_boss": is_boss, "username": username})



def identify_user(state: BotState) -> BotState:
    user_id = state["user_id"]
    is_boss = state["is_boss"]
    username = state["username"]
    if state["user_id"] == "":
        user_id = "boss" if BOSS_NAME in state["input_msg"] else "other"
        is_boss = user_id == "boss"
        username_result = new_langchain_utils.identify_user(state["input_msg"])
        username = username_result["username"]
        print("# user_id: ", user_id)
        print("# is_boss: ", is_boss)
        print("# username: ", username)
    return {**state, "user_id": user_id, "is_boss": is_boss, "username": username}

def identify_intent(state: BotState) -> BotState:
    intent_json = new_langchain_utils.identify_intent(state["input_msg"])
    # Only updates intention if identify_intent is a valid intent
    if intent_json["intent"] in ["schedule", "list", "cancel", "check", "update"]:
        intent = intent_json["intent"]
    else: # keeps the old value
        intent = state["user_intent"]
    print("# User intent: ", intent)
    return {**state, "user_intent": intent}

def choose_action(state: BotState) -> BotState:
    def has_required_fields(intent: str, action_input: dict) -> bool:
        def is_falsy(value):
            return value == "" or value == "unknown" or value == []
        match intent:
            case "schedule":
                return all([
                    not is_falsy(action_input.get("event_name")),
                    not is_falsy(action_input.get("start_time")),
                    not is_falsy(action_input.get("end_time")),
                    not is_falsy(action_input.get("invited_people")),
                ])
            case "cancel" | "check" | "update":
                return not is_falsy(action_input.get("event_name"))
            case "list":
                return True  # nothing required for list
            case _:
                return False
    action = "follow_up"
    if not state["greeted"]:
        action = "greet"
    elif state["user_intent"] in ["schedule", "list", "cancel", "check", "update"]:
        action_input_json = new_langchain_utils.extract_action_input(state["input_msg"], state["context"], state["user_intent"])
        print("Extracted action input:", action_input_json)
        state["action_input"] = action_input_json  # optionally update state with extracted input
        if has_required_fields(state["user_intent"], action_input_json):
            action = "take_intent"
        else:
            action = "request_more_info"
    else:
        action = "follow_up"
    return {**state, "chosen_action": action}

def act(state: BotState) -> BotState:
    intent = state["user_intent"]
    chosen_action = state["chosen_action"]
    if chosen_action == "take_intent":
        # Retrieve action_input from the state
        action_input = state["action_input"]
        if intent == "schedule":
            try:
                result = schedule_meeting(action_input)
            except Exception as e:
                result = {
                    "success": False,
                    "info": f"An error occurred while scheduling the meeting: {e}"
                }
        elif intent == "list":
            try:
                result = list_meetings(action_input)
            except Exception as e:
                result = {
                    "success": False,
                    "info": f"An error occurred while listing the meetings: {e}"
                }
        elif intent == "cancel":
            try:
                result = cancel_meeting(action_input)
            except Exception as e:
                result = {
                    "success": False,
                    "info": f"An error occurred while canceling the meeting: {e}"
                }
        elif intent == "check":
            try:
                result = check_meeting(action_input)
            except Exception as e:
                result = {
                    "success": False,
                    "info": f"An error occurred while checking the meeting: {e}"
                }
        elif intent == "update":
            try:
                result = update_meeting(action_input)
            except Exception as e:
                result = {
                    "success": False,
                    "info": f"An error occurred while updating the meeting: {e}"
                } 
        else:
            result = {
                "success": False,
                "info": "Unknown intent, cannot process."
            }
    else:
        result = state["action_result"]
    return {**state, "action_result": result}

def gen_response(state: BotState) -> BotState:
    greeted = state["greeted"]
    if state["chosen_action"] == "greet":
        response = new_langchain_utils.greet_user(
        user_input=state["input_msg"],
        username=state["username"],
        is_boss=state["is_boss"]
        )
        greeted = True
    elif state["chosen_action"] == "request_more_info":
        response = new_langchain_utils.generate_missing_info_request(
        user_input=state["input_msg"],
        intent=state["user_intent"],
        action_input=state["action_input"]
        )
    elif state["chosen_action"] == "take_intent":
        response = new_langchain_utils.generate_confirmation_response(
        user_input=state["input_msg"],
        intent=state["user_intent"],
        action_input=state["action_input"],
        action_result=state["action_result"]
        )
    elif state["chosen_action"] == "follow_up":
        response = new_langchain_utils.follow_up(
        user_input=state["input_msg"],
        username=state["username"],
        is_boss=state["is_boss"]
        )
    else:
        response = "other answer"
    return {**state, "response": response, "greeted": greeted}

def send_response(state: BotState) -> BotState:
    print(f"Bot: {state['response']}")
    # Add user input and bot response to context
    updated_context = state["context"]
    updated_context.append({"role": "assistant", "content": state['response']})
    return {**state, "context": updated_context}


# Google Calendar Part

# Function to handle scheduling a meeting
def schedule_meeting(action_input: ActionInput) -> ActionResult:
    event_name = action_input.get("event_name")
    start_time = action_input.get("start_time")
    end_time = action_input.get("end_time")
    description = action_input.get("description", "")
    invited_people = action_input.get("invited_people", [])
    location = action_input.get("location", "")
    # Add the new event to the calendar (list)
    new_event = ActionInput(
        event_name=event_name,
        start_time=start_time,
        end_time=end_time,
        description=description,
        invited_people=invited_people,
        location=location
    )
    gresult = google_calendar.create_event(summary=event_name, start_time=start_time, end_time=end_time, description=description, location=location, attendees_emails=invited_people)
    success = (gresult["status"] == "confirmed")
    google_meet_link = gresult["hangoutLink"]
    result = {
        "success": success,
        "info": f"The meeting '{event_name}' has been scheduled from {start_time} to {end_time}. Participants: {', '.join(invited_people)}. Event description: {description}, Location: {location}. Google Meet link: {google_meet_link}"
    }
    return result

# Function to handle listing all meetings
def list_meetings(action_input: ActionInput) -> dict:
    start_time = action_input.get("start_time")
    end_time = action_input.get("end_time")
    events = google_calendar.list_events(time_min=start_time, time_max=end_time, max_results=25, include_past=True)
    
    success = True
    info = ""
    
    if not events or events == []:
        info = "No events found."
    else:
        meetings_list = []
        for event in events:
            summary = event.get('summary', 'No Title')
            start = event.get('start', {}).get('dateTime', 'Unknown Start')
            end = event.get('end', {}).get('dateTime', 'Unknown End')
            attendees = event.get('attendees', [])
            participants = ", ".join([attendee.get('email', 'Unknown') for attendee in attendees])
            
            meeting_details = f"Meeting: {summary}, Time: {start} to {end}, Participants: {participants}"
            meetings_list.append(meeting_details)
        
        info = "\n".join(meetings_list)
    
    result = {
        "success": success,
        "info": info
    }
    return result

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def find_meeting_id(action_input: ActionInput) -> List[str]:
    start_time = action_input.get("start_time")
    end_time = action_input.get("end_time")
    
    events = google_calendar.list_events(
        time_min=start_time,
        time_max=end_time,
        max_results=50,
        include_past=True
    )

    if not events:
        print("No events found in the given time range.")
        return []

    # Prepare the target text based on selected fields
    action_input_text = f"""
    Event Name: {action_input.get('event_name', '')}
    Description: {action_input.get('description', '')}
    Invited People: {', '.join(action_input.get('invited_people', []))}
    """
    target_embedding = new_langchain_utils.get_embedding(action_input_text.strip())

    scores = []
    event_ids = []

    # Parse the action_input start_time
    action_input_start_dt = datetime.fromisoformat(start_time) if start_time else None

    for idx, event in enumerate(events):
        event_text = f"""
        Event Name: {event.get('summary', '')}
        Description: {event.get('description', '')}
        Invited People: {', '.join([attendee.get('email', '') for attendee in event.get('attendees', [])])}
        """
        event_embedding = new_langchain_utils.get_embedding(event_text.strip())
        embedding_similarity = cosine_similarity(target_embedding, event_embedding)
        
        # Default to embedding similarity
        final_score = embedding_similarity
        time_similarity = None

        if action_input_start_dt:
            event_start_str = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
            if event_start_str:
                event_start_dt = datetime.fromisoformat(event_start_str)
                if event_start_dt.tzinfo is not None:
                    event_start_dt = event_start_dt.replace(tzinfo=None)
                minutes_difference = abs((event_start_dt - action_input_start_dt).total_seconds()) / 60
                k = 0.05
                time_similarity = math.exp(-k * minutes_difference)
                final_score = 0.2 * embedding_similarity + 0.8 * time_similarity

        event_id = event.get('id')
        
        # Print event info
        print(f"[Event {idx+1}] ID: {event_id}")
        print(f"Embedding Similarity: {embedding_similarity:.4f}")
        if time_similarity is not None:
            print(f"Time Similarity: {time_similarity:.4f}")
        print(f"Final Combined Score: {final_score:.4f}")
        print(f"Title: {event.get('summary', '')}")
        print(f"Description: {event.get('description', '')}")
        print("-" * 50)
        
        scores.append(final_score)
        event_ids.append(event_id)

    # Find the highest final score
    max_score = max(scores)
    best_match_indexes = [i for i, score in enumerate(scores) if score == max_score]

    matched_ids = [event_ids[i] for i in best_match_indexes]
    
    return matched_ids

# Function to handle canceling a meeting
def cancel_meeting(action_input: ActionInput) -> str:
    success = False
    info = "No meeting found with the name '{event_name}'."
    event_name = action_input.get("event_name")
    
    # Search for the meeting to cancel
    for i, event in enumerate(calendar_events):
        if event["event_name"] == event_name:
            del calendar_events[i]
            success = True
            info = f"The meeting '{event_name}' has been canceled."
    
    result = {
        "success": success,
        "info": info
    }
    return result

# Function to handle checking a meeting's availability
def check_meeting(action_input: ActionInput) -> str:
    success = False
    info = f"No meeting found with the name '{event_name}'."
    event_name = action_input.get("event_name")
    
    # Search for the meeting and return details
    for event in calendar_events:
        if event["event_name"] == event_name:
            success = True
            info = f"The details of the meeting '{event_name}' are: Start: {event['start_time']}, End: {event['end_time']}, Participants: {', '.join(event['invited_people'])}, Meet Link: (not yet)"
    
    result = {
        "success": success,
        "info": info
    }
    return result

# Function to handle updating a meeting
def update_meeting(action_input: ActionInput) -> str:
    success = False
    info = ""
    event_name = action_input.get("event_name")
    updated_event = None
    
    # Find and update the event
    for event in calendar_events:
        if event["event_name"] == event_name:
            updated_event = event
            if action_input.get("start_time"):
                event["start_time"] = action_input["start_time"]
            if action_input.get("end_time"):
                event["end_time"] = action_input["end_time"]
            if action_input.get("description"):
                event["description"] = action_input["description"]
            if action_input.get("invited_people"):
                event["invited_people"] = action_input["invited_people"]
            break
    
    if updated_event:
        success = True
        info = f"The meeting '{event_name}' has been updated. New details: Start: {updated_event['start_time']}, End: {updated_event['end_time']}, Participants: {', '.join(updated_event['invited_people'])}"
    else:
        success = False
        info = f"No meeting found with the name '{event_name}' to update."
    result = {
        "success": success,
        "info": info
    }
    return result

# ----- Build the graph -----
graph_builder = StateGraph(BotState)
graph_builder.add_node("identify_user", identify_user)
graph_builder.add_node("identify_intent", identify_intent)
graph_builder.add_node("choose_action", choose_action)
graph_builder.add_node("act", act)
graph_builder.add_node("gen_response", gen_response)
graph_builder.add_node("send_response", send_response)

graph_builder.set_entry_point("identify_user")
graph_builder.add_edge("identify_user", "identify_intent")
graph_builder.add_edge("identify_intent", "choose_action")
graph_builder.add_edge("choose_action", "act")
graph_builder.add_edge("act", "gen_response")
graph_builder.add_edge("gen_response", "send_response")
graph_builder.add_edge("send_response", END)

graph = graph_builder.compile()

# ----- Run the terminal loop -----

if __name__ == "__main__":
    # Accessing multi-line prompts
    def_prompt = prompts.def_prompt
    time_prompt = prompts.time_prompt
    tone_prompt = prompts.tone_prompt
    user_boss = prompts.user_boss
    user_other = prompts.user_other

    current_context: List[ChatMessage] = [
        {"role": "system", "content": def_prompt},
        {"role": "system", "content": time_prompt}
    ]

    # Initialize the result object with the desired structure
    result = {
        "input_msg": "",
        "context": current_context,
        "is_boss": False,
        "greeted": False,
        "user_id": "",
        "username": "",
        "user_intent": "none",
        "chosen_action": "take_intent",
        "action_input": {
            "event_name": "",
            "start_time": "",
            "end_time": "",
            "description": "",
            "invited_people": [],
            "location": ""
        },
        "action_result": {
            "success": False,
            "info": ""
        },
        "response": ""
    }

    # Main interaction loop
    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            break

        # Add user input to the context
        current_context.append({"role": "user", "content": user_input})

        # Simulate graph invocation (replace with actual graph logic)
        result = graph.invoke({
            **result,
            "input_msg": user_input,
            "context": current_context,
            "response": "",
            "chosen_action": "",
            "action_result": {
                "success": False,
                "info": ""
            },
            "response": ""
        })

        # Output the bot's response (replace with actual logic to generate the response)
        print(f"Bot: {result['response']}")



# Nodes:
# identify_user (use LLM to extract info)
# identify_intent (use LLM to identify what the user wants)
# choose_action (use LLM to choose the best action)
# act (use LLM to format the data to be passed to Google Calendar functions)
# gen_response (use LLM to generate the response)
# send_response

#class BotState(TypedDict):
#    input_msg: str
#    context: str[]
#    is_boss: bool
#    user_id: str
#    user_intent: (list of options)
#    chosen_action: (list of options)
#    action_result: str
#    response: str

# Possible users: boss and other
# Possible values of user_intent: schedule, list, cancel, check, update, none
# Possible actions: greet, take_intent, request_more_info, follow_up
# Possible responses: greeting, action_result, info_request, follow_up 
