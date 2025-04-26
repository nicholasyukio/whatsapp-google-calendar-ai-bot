from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from typing import TypedDict, List, Literal
import new_langchain_utils

BOSS_NAME = "Nicholas"

class ActionInput(TypedDict, total=False):  # total=False makes all fields optional
    event_name: str
    start_time: str
    end_time: str
    description: str
    invited_people: List[str]
    meet_link: str

# ----- Define BotState -----
class BotState(TypedDict):
    input_msg: str
    context: List[str]
    is_boss: bool
    greeted: bool
    user_id: str
    username: str
    user_intent: Literal["schedule", "list", "cancel", "check", "update", "none"]
    chosen_action: Literal["greet", "take_intent", "request_more_info", "follow_up"]
    action_input: ActionInput
    action_result: str
    response: str

# ----- Simulated Calendar -----
calendar_events = []

# ----- Nodes -----

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
            return value == "" or value == "unknown"
        match intent:
            case "schedule":
                return all([
                    not is_falsy(action_input.get("event_name")),
                    not is_falsy(action_input.get("start_time")),
                    not is_falsy(action_input.get("end_time")),
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
                result = f"An error occurred while scheduling the meeting: {e}"
        elif intent == "list":
            try:
                result = list_meetings()
            except Exception as e:
                result = f"An error occurred while listing the meetings: {e}"
        elif intent == "cancel":
            try:
                result = cancel_meeting(action_input)
            except Exception as e:
                result = f"An error occurred while canceling the meeting: {e}"
        elif intent == "check":
            try:
                result = check_meeting(action_input)
            except Exception as e:
                result = f"An error occurred while checking the meeting: {e}"
        elif intent == "update":
            try:
                result = update_meeting(action_input)
            except Exception as e:
                result = f"An error occurred while updating the meeting: {e}" 
        else:
            result = "Unknown intent, cannot process."
    else:
        result = ""
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
    updated_context = state["context"] + [
        f"User: {state['input_msg']}",
        f"Bot: {state['response']}"
    ]
    return {**state, "context": updated_context}


# Google Calendar Part

# Function to handle scheduling a meeting
def schedule_meeting(action_input: ActionInput) -> str:
    event_name = action_input.get("event_name")
    start_time = action_input.get("start_time")
    end_time = action_input.get("end_time")
    description = action_input.get("description", "")
    invited_people = action_input.get("invited_people", [])
    meet_link = action_input.get("meet_link", "")
    
    # Check for conflicts with existing events
    for event in calendar_events:
        if event["start_time"] == start_time and event["end_time"] == end_time:
            return f"There's already a meeting scheduled from {start_time} to {end_time}."
    
    # Add the new event to the calendar (list)
    new_event = ActionInput(
        event_name=event_name,
        start_time=start_time,
        end_time=end_time,
        description=description,
        invited_people=invited_people,
        meet_link=meet_link
    )
    calendar_events.append(new_event)
    
    return f"Your meeting '{event_name}' has been scheduled from {start_time} to {end_time}. Participants: {', '.join(invited_people)}"

# Function to handle listing all meetings
def list_meetings() -> str:
    if not calendar_events:
        return "There are no upcoming meetings."
    
    meetings_list = []
    for event in calendar_events:
        meeting_details = f"Meeting: {event['event_name']}, Time: {event['start_time']} to {event['end_time']}, Participants: {', '.join(event['invited_people'])}"
        meetings_list.append(meeting_details)
    
    return "\n".join(meetings_list)

# Function to handle canceling a meeting
def cancel_meeting(action_input: ActionInput) -> str:
    event_name = action_input.get("event_name")
    
    # Search for the meeting to cancel
    for i, event in enumerate(calendar_events):
        if event["event_name"] == event_name:
            del calendar_events[i]
            return f"The meeting '{event_name}' has been canceled."
    
    return f"No meeting found with the name '{event_name}'."

# Function to handle checking a meeting's availability
def check_meeting(action_input: ActionInput) -> str:
    event_name = action_input.get("event_name")
    
    # Search for the meeting and return details
    for event in calendar_events:
        if event["event_name"] == event_name:
            return f"The details of the meeting '{event_name}' are: Start: {event['start_time']}, End: {event['end_time']}, Participants: {', '.join(event['invited_people'])}, Meet Link: {event.get('meet_link', 'N/A')}"
    
    return f"No meeting found with the name '{event_name}'."

# Function to handle updating a meeting
def update_meeting(action_input: ActionInput) -> str:
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
            if action_input.get("meet_link"):
                event["meet_link"] = action_input["meet_link"]
            break
    
    if updated_event:
        return f"The meeting '{event_name}' has been updated. New details: Start: {updated_event['start_time']}, End: {updated_event['end_time']}, Participants: {', '.join(updated_event['invited_people'])}"
    
    return f"No meeting found with the name '{event_name}' to update."

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
    current_context: List[str] = []
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
            "meet_link": ""
        },
        "action_result": "",
        "response": ""
    }

    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            break

        result = graph.invoke({
            **result,
            "input_msg": user_input,
            "response": "",
            "user_intent": "",
            "chosen_action": "",
            "action_result": "",
            "response": ""
        })  



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
