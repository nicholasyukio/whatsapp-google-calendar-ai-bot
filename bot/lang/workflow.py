from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Literal
from datetime import datetime, timedelta, time
import math
import google_calendar
import numpy as np
import prompts
import json
from openai import OpenAI
from dotenv import load_dotenv
import os
import database

load_dotenv()

BOSS_NAME = "Nicholas"

class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

class ActionInput(TypedDict, total=False):  # total=False makes all fields optional
    event_id: str
    event_name: str
    start_time: str
    end_time: str
    description: str
    invited_people: List[str]
    location: str
    is_update: bool

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
    user_email: str
    username: str
    user_intent: Literal["schedule", "list", "cancel", "update", "none"]
    chosen_action: Literal["greet", "take_intent", "request_more_info", "follow_up"]
    action_input: ActionInput
    action_result: ActionResult
    response: str
    updated_at_utc: str

# ----- Nodes -----

# Define the main Bot class
class Bot:
    # Constructor
    def __init__(self, state: BotState):
        self.state = state
        self.state_graph = StateGraph(BotState)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.blocked_times = {
            "weekdays": [
                (time(0, 0), time(8, 0)),
                (time(22, 0), time(23, 59)),
            ],
            "weekends": "all",
        }
        self.prompts = {
            "default": prompts.def_prompt,
            "time_handling": prompts.time_prompt,
            "tone_adjustment": prompts.tone_prompt,
            "user_boss": prompts.user_boss,
            "user_other": prompts.user_other,
            "greet_base": prompts.greet_base,
            "follow_up_base": prompts.follow_up_base,
            "identify_user_base": prompts.identify_user_base,
            "identify_intent_base": prompts.identify_intent_base,
            "extract_action_schedule": prompts.extract_action_schedule,
            "extract_action_list": prompts.extract_action_list,
            "extract_action_other": prompts.extract_action_other,
            "generate_missing_info_request_base": prompts.generate_missing_info_request_base,
            "generate_confirmation_response_for_list": prompts.generate_confirmation_response_for_list,
            "generate_confirmation_response_for_other": prompts.generate_confirmation_response_for_other,
            "generate_confirmation_response_for_fail": prompts.generate_confirmation_response_for_fail,

        }
        self.profiles = {
            "greet_user": ["default", "greet_base", "time_handling", "tone_adjustment"],
            "follow_up": ["default", "follow_up_base", "time_handling", "tone_adjustment"],
            "identify_user": ["default", "identify_user_base"],
            "identify_intent": ["default", "identify_intent_base"],
            "extract_action_input_for_schedule": ["default", "time_handling", "extract_action_schedule"],
            "extract_action_input_for_list": ["default", "time_handling", "extract_action_list"],
            "extract_action_input_for_other": ["default", "time_handling", "extract_action_other"],
            "extract_action_input_for_new_info": ["default", "time_handling", "extract_action_new_info"],
            "generate_missing_info_request": ["default", "generate_missing_info_request_base", "time_handling", "tone_adjustment"],
            "generate_confirmation_response_for_list": ["default", "generate_confirmation_response_for_list", "time_handling", "tone_adjustment"],
            "generate_confirmation_response_for_other": ["default", "generate_confirmation_response_for_other", "time_handling", "tone_adjustment"],
            "generate_confirmation_response_for_fail": ["default", "generate_confirmation_response_for_fail", "time_handling", "tone_adjustment"]
        }

    # Default blocked times
    def is_time_blocked(self, check_time: datetime) -> bool:
        weekday = check_time.weekday()
        t = check_time.time()

        if weekday >= 5:  # Saturday=5, Sunday=6
            return self.blocked_times["weekends"] == "all"

        for start, end in self.blocked_times["weekdays"]:
            if start <= t <= end:
                return True
        return False

    # LLM (OpenAI)
    def completion(self, state, system_prompts: List[str] = None, profile: str = None, is_json: bool = False, **kwargs) -> str:
        """Wrapper for OpenAI chat completions, with flexible system prompts."""
        messages = []
        if state["is_boss"]:
            messages.append({"role": "system", "content": self.prompts["user_boss"]})
        else:
            messages.append({"role": "system", "content": self.prompts["user_other"]})
        # Select system prompts
        if profile:
            selected_prompts = self.profiles[profile]
        else:
            selected_prompts = system_prompts or []

        # Add system prompts
        for prompt_name in selected_prompts:
            system_prompt = self.prompts[prompt_name]
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

        # Add chat context (user/assistant messages from state)
        messages.extend(state["context"])
        response = self.client.chat.completions.create(
            model="gpt-4",  # or gpt-3.5-turbo
            messages=messages,
            temperature=0.7,
            **kwargs
        )
        if is_json:
            content = response.choices[0].message.content
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                print("Invalid JSON. Raw content:", content)
                parsed = {}
            return parsed
        else:
            return response.choices[0].message.content.strip()

    def greet_user(self, state):
        return self.completion(state, profile="greet_user")
    
    def follow_up(self, state):
        return self.completion(state, profile="follow_up")
    
    def identify_user(self, state):
        return self.completion(state, profile="identify_user", is_json=True)
    
    def identify_intent(self, state):
        return self.completion(state, profile="identify_intent", is_json=True)
    
    def extract_action_input(self, state):
        full_fields = {
            "event_id": "",
            "event_name": "",
            "start_time": "",
            "end_time": "",
            "description": "",
            "invited_people": [],
            "location": "",
            "is_update": False
        }
        if state["user_intent"] == "schedule":
            expected_fields = ["event_name", "start_time", "end_time", "description", "invited_people", "location"]
            profile = "extract_action_input_for_schedule"
        elif state["user_intent"] == "list":
            expected_fields = ["start_time", "end_time"]
            profile = "extract_action_input_for_list"
        elif state["user_intent"] == "cancel":
            expected_fields = ["event_id", "start_time", "end_time"]
            profile = "extract_action_input_for_other"
        elif state["user_intent"] == "update":
            if state["action_input"]["is_update"]:
                # in this case, extract action input for new values to update
                expected_fields = []
                profile = "extract_action_input_for_new_info"
            else:
                # in this case, extract action input for listing the possible events to update
                expected_fields = ["event_id", "start_time", "end_time"]
                profile = "extract_action_input_for_other"
        else:
            return full_fields
        parsed = self.completion(state, profile=profile, is_json=True)
        result = full_fields.copy()
        for field in expected_fields:
            try:
                result[field] = parsed[field]
            except Exception as e:
                print(f"Error encountered in JSON:{e}")
                result[field] = full_fields[field]
        if state["user_intent"] == "list":
            std_start_datetime = datetime.now()
            std_start_datetime_iso = std_start_datetime.isoformat()
            std_end_datetime = std_start_datetime + timedelta(days=7)
            std_end_datetime_iso = std_end_datetime.isoformat()
            if result["start_time"] == "unknown": result["start_time"] = std_start_datetime_iso
            if result["end_time"] == "unknown": result["end_time"] = std_end_datetime_iso
        return result
    
    def generate_missing_info_request(self, state) -> str:
        # if missing info is time, suggest time slots
        if state["user_intent"] == "schedule" and state["action_input"]["start_time"] == "":
            suggested_time_slots = self.suggest_time_slots(state, state["action_input"])
            if suggested_time_slots["success"]:
                info = suggested_time_slots["info"]
                content = f"Time slot suggestions: {info}"
                state["context"].append({"role": "assistant", "content": content})
        return self.completion(state, profile="generate_missing_info_request")
    
    def generate_confirmation_response(self, state) -> str:
        success = state["action_result"]["success"]
        info = state["action_result"]["info"]
        intent = state["user_intent"]
        if success:
            if intent == "list":
                profile = "generate_confirmation_response_for_list"
            else:
                profile = "generate_confirmation_response_for_other"
        else:
            profile = "generate_confirmation_response_for_fail"
        return self.completion(state, profile=profile)

    # LangGraph nodes and edges

    def n_identify_user(self, state):
        print("n_identify_user")
        print(state)
        user_id = state["user_id"]
        is_boss = state["is_boss"]
        username = state["username"]
        print("Node n_identify_user")
        if state["user_id"] == "":
            user_id = "boss" if BOSS_NAME in state["input_msg"] else "other"
            is_boss = user_id == "boss"
            username_result = self.identify_user(state)
            try:
                username = username_result["username"]
            except Exception as e:
                print(f"Unexpected error with JSON: {e}")
            print(username_result)
            print("# user_id: ", user_id)
            print("# is_boss: ", is_boss)
            print("# username: ", username)

        state.update({"user_id": user_id, "is_boss": is_boss, "username": username})
        return state

    def n_identify_intent(self, state):
        print("Node n_identify_intent")
        intent_json = self.identify_intent(state)
        try:
            if intent_json["intent"] in ["schedule", "list", "cancel", "update"]:
                intent = intent_json["intent"]
                print("# User intent: ", intent)
                state["user_intent"] = intent
        except Exception as e:
            print(f"Unexpected error with JSON: {e}")
            intent = state["user_intent"]
        return state

    def n_choose_action(self, state):
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
                case "cancel" | "update":
                    return not is_falsy(action_input.get("event_id"))
                case "list":
                    return True
                case _:
                    return False

        action = "follow_up"
        if not state["greeted"]:
            action = "greet"
        elif state["user_intent"] in ["schedule", "list", "cancel", "update"]:
            action_input_json = self.extract_action_input(state)
            print("Extracted action input:", action_input_json)
            state["action_input"] = action_input_json  # optionally update state with extracted input
            if has_required_fields(state["user_intent"], action_input_json) or state["user_intent"] in ["cancel", "update"]:
                action = "take_intent"
            else:
                action = "request_more_info"
        else:
            action = "follow_up"

        state["chosen_action"] = action
        return state

    def n_act(self, state):
        intent = state["user_intent"]
        chosen_action = state["chosen_action"]
        if chosen_action == "take_intent":
            # Retrieve action_input from the state
            action_input = state["action_input"]
            try:
                if intent == "schedule":
                    result = self.schedule_meeting(state, action_input)
                elif intent == "list":
                    result = self.list_meetings(state, action_input)
                elif intent == "cancel":
                    result = self.cancel_meeting(state)
                elif intent == "update":
                    result = self.update_meeting(state, action_input)
                else:
                    result = {
                        "success": False,
                        "info": "Unknown intent, cannot process."
                    }
            except Exception as e:
                result = {
                    "success": False,
                    "info": f"An error occurred while processing the meeting: {e}"
                }
        else:
            result = state["action_result"]
        if result["success"]:
            info_to_context = {"role": "assistant", "content": f"[INFO] Action {intent} was SUCCESSFUL, details: {result.get('info', 'No details available')}"}
        else:
            info_to_context = {"role": "assistant", "content": f"[INFO] Action {intent} was NOT SUCCESSFUL, details: {result.get('info', 'No details available')}"}
        state["context"].append(info_to_context)
        state["action_result"] = result
        return state

    def n_gen_response(self, state):
        greeted = state["greeted"]
        if state["chosen_action"] == "greet":
            response = self.greet_user(state)
            greeted = True
        elif state["chosen_action"] == "request_more_info":
            response = self.generate_missing_info_request(state)
        elif state["chosen_action"] == "take_intent":
            response = self.generate_confirmation_response(state)
        elif state["chosen_action"] == "follow_up":
            response = self.follow_up(state)
        else:
            response = "other answer"

        state["response"] = response
        state["greeted"] = greeted
        return state

    def n_send_response(self, state):
        print(f"Bot: {state['response']}")
        # Add user input and bot response to context
        updated_context = state["context"]
        updated_context.append({"role": "assistant", "content": state['response']})
        state["context"] = updated_context
        return state

    # Google Calendar Part

    # Function to handle scheduling a meeting
    def schedule_meeting(self, state, action_input: ActionInput) -> ActionResult:
        event_name = action_input.get("event_name")
        start_time = action_input.get("start_time")
        end_time = action_input.get("end_time")
        description = action_input.get("description", "")
        invited_people = action_input.get("invited_people", [])
        location = action_input.get("location", "")
        google_meet_link = ""

        start_time_f = datetime.fromisoformat(start_time)
        blocked = self.is_time_blocked(start_time_f)

        if state["is_boss"] or not blocked:
            # Assuming google_calendar.create_event is an external function:
            gresult = google_calendar.create_event(
                summary=event_name,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                attendees_emails=invited_people
            )
            
            success = (gresult["status"] == "confirmed")
            google_meet_link = gresult.get("hangoutLink", "")
            
            result = {
                "success": success,
                "info": f"The meeting '{event_name}' scheduled from {start_time} to {end_time}. "
                        f"Participants: {', '.join(invited_people)}. Event description: {description}, "
                        f"Location: {location}. Google Meet link: {google_meet_link}"
            }
        else:
            result = {
                "success": False,
                "info": f"The meeting '{event_name}' scheduled from {start_time} to {end_time}. "
                        f"Participants: {', '.join(invited_people)}. Event description: {description}, "
                        f"Location: {location}. Google Meet link: {google_meet_link}"
                        f"Failure reason: Time slot not available"
            }
        
        return result

    def suggest_time_slots(self, state, action_input: ActionInput, slot_duration_minutes: int = 60) -> ActionResult:
        start_time_str = action_input.get("start_time")
        end_time_str = action_input.get("end_time")

        if not start_time_str or not end_time_str:
            return {
                "success": False,
                "info": "Start time and end time are required to suggest time slots."
            }
        
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)

        events = google_calendar.list_events(
            time_min=start_time_str, 
            time_max=end_time_str, 
            max_results=100,
            include_past=False
        )

        busy_times = []
        for event in events:
            event_start = event.get('start', {}).get('dateTime')
            event_end = event.get('end', {}).get('dateTime')
            if event_start and event_end:
                busy_times.append((
                    datetime.fromisoformat(event_start),
                    datetime.fromisoformat(event_end)
                ))
        
        # Sort busy_times by start
        busy_times.sort(key=lambda x: x[0])

        suggestions = []
        current_time = start_time

        while current_time + timedelta(minutes=slot_duration_minutes) <= end_time:
            slot_end_time = current_time + timedelta(minutes=slot_duration_minutes)

            # Check if the current slot overlaps with any busy event
            overlapping = False
            for busy_start, busy_end in busy_times:
                if not (slot_end_time <= busy_start or current_time >= busy_end):
                    overlapping = True
                    break

            # Check if the current time is within blocked times
            blocked = self.is_time_blocked(current_time)

            if not overlapping and not blocked:
                suggestions.append(f"{current_time.strftime('%Y-%m-%d %H:%M')} to {slot_end_time.strftime('%H:%M')}")

            current_time += timedelta(minutes=slot_duration_minutes)

        if not suggestions:
            info = "No available time slots found."
        else:
            info = "Here are some available time slots:\n" + "\n".join(suggestions)

        return {
            "success": True,
            "info": info
        }

    def list_meetings(self, state, action_input: ActionInput, user_email: str = "", include_past: bool = True) -> ActionResult:
        start_time = action_input.get("start_time")
        end_time = action_input.get("end_time")
        
        # Assuming google_calendar.list_events is an external function:
        events = google_calendar.list_events(
            time_min=start_time, 
            time_max=end_time, 
            max_results=25, 
            include_past=include_past
        )
        
        success = True
        info = ""
        
        if not events or events == []:
            info = "No events found."
        else:
            meetings_list = []
            k = 1
            for event in events:
                event_id = event.get('id')
                summary = event.get('summary', 'No Title')
                start = event.get('start', {}).get('dateTime', 'Unknown Start')
                end = event.get('end', {}).get('dateTime', 'Unknown End')
                attendees = event.get('attendees', [])
                list_event = False
                if user_email != "":
                    if user_email in attendees:
                        list_event = True
                elif state["is_boss"]:
                   list_event = True

                if list_event:
                    participants = ", ".join([attendee.get('email', 'Unknown') for attendee in attendees])
                    meeting_details = f"#{k}: Id: {event_id}, Meeting: {summary}, Time: {start} to {end}, Participants: {participants}"
                    meetings_list.append(meeting_details)
                    k = k + 1
            
            info = "\n".join(meetings_list)
        
        result = {
            "success": success,
            "info": info
        }
        
        return result

    def find_meeting_id(self, state, attendee_email: str = "") -> List[str]:
        """
        Finds meetings based on the user's action input and compares the events in the given time range.
        
        Returns:
            List[str]: List of event IDs that are the best match.
        """
        action_input = state["action_input"]
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
        
        event_data_list = []
        event_info_strings = []

        for event in events:
            attendees_email_list = [attendee.get('email', '') for attendee in event.get('attendees', [])]
            event_id = event.get('id')
            event_title = event.get('summary', '')
            event_start = event.get('start', '')
            event_end = event.get('end', '')
            event_description = event.get('description', '')
            event_location = event.get('location', '')
            event_data = {
                        "event_id": event_id,
                        "event_name": event_title,
                        "start_time": event_start,
                        "end_time": event_end,
                        "description": event_description,
                        "invited_people": attendees_email_list,
                        "location": event_location
            }
            if state["is_boss"]:
                if attendee_email == "":
                    event_data_list.append(event_data)
                else:
                    if attendee_email in attendees_email_list:
                        event_data_list.append(event_data)
            else:
                if attendee_email in attendees_email_list:
                    event_data_list.append(event_data)

            # Create a human-readable string to describe the event
            event_info_strings.append(f"Event '{event_title}' is scheduled from {event_start} to {event_end}. "
                                    f"Description: {event_description}. Location: {event_location} Event ID: {event_id}")

        # Combine the event details into a single string
        event_info_str = "\n".join(event_info_strings)

        # Add the information to the context
        info_to_context = {
            "role": "assistant",
            "content": f"[INFO] Here are the events found: \n{event_info_str}"
        }

        state["context"].append(info_to_context) 
        
        return event_data_list

    def cancel_meeting(self, state) -> dict:
        """
        Cancels a meeting based on the event name from the state.
        
        Returns:
            dict: A dictionary containing success status and information message.
        """
        action_input = state["action_input"]
        event_name = action_input.get("event_name")

        event_id = action_input.get("event_id")
        if event_id:
            ### STOPPED HERE 28/04/25 00:29
            success = google_calendar.cancel_event(event_id)
            # It seems success is not returning the real status
            if success:
                info = f"The meeting '{event_name}' has been successfully canceled."
                print(f"The meeting '{event_name}' with id '{event_id}' has been successfully canceled.")
            else:
                info = f"Failed to cancel the meeting '{event_name}'."
            # Update the state with the canceled meeting result
            result = {
                "success": success,
                "info": info
            }
        else:
            meetings_list = self.list_meetings(state, state["action_input"], include_past=False)
            success = False
            info = "[INFO] (Cancelation pending) Meetings the user can cancel:\n" + meetings_list["info"]
            result = {
                "success": success,
                "info": info
            }
        return result

    def update_meeting(self, state, action_input: ActionInput) -> str:
        event_id = action_input.get("event_id", None)
        event_name = action_input.get("event_name", "")
        start_time = action_input.get("start_time", "")
        end_time = action_input.get("end_time", "")
        description = action_input.get("description", "")
        location = action_input.get("location", "")
        attendees_emails = action_input.get("invited_people", )
        is_update = action_input.get("is_update", False)

        success = False
        info = ""

        if event_id:
            if is_update:
                    gresult = google_calendar.update_event(
                    event_id=event_id,
                    title=event_name,
                    start_time=start_time,
                    end_time=end_time,
                    description=description,
                    location=location,
                    attendees_emails=attendees_emails
                    )
                    if gresult:
                        success = True
                        info = f"""The meeting '{event_name}' has been updated successfully. New details: Start: {start_time}, End: {end_time}, 
                        Participants: {', '.join(attendees_emails)}"""
                    else:
                        info = f"Failed to update the meeting '{event_name}' in Google Calendar."
            else:
                state["action_input"] = {
                    **state["action_input"],
                    "event_name": "",
                    "start_time": "",
                    "end_time": "",
                    "description": "",
                    "invited_people": [],
                    "location": "",
                    "is_update": True
                }
                success = False
                info = """[INFO] (Update pending) The event the user wants to update was identified, but the user needs to clearly confirm 
                what they want to change"""
        else:
            meetings_list = self.list_meetings(state, state["action_input"], include_past=False)
            success = False
            info = "[INFO] (Update pending) Meetings the user can update:\n" + meetings_list["info"]

        # Return the result
        result = {
            "success": success,
            "info": info
        }
        return result

    # Method to build the graph inside the Bot class
    def build_graph(self):
        self.state_graph.add_node("n_identify_user", self.n_identify_user)
        self.state_graph.add_node("n_identify_intent", self.n_identify_intent)
        self.state_graph.add_node("n_choose_action", self.n_choose_action)
        self.state_graph.add_node("n_act", self.n_act)
        self.state_graph.add_node("n_gen_response", self.n_gen_response)
        self.state_graph.add_node("n_send_response", self.n_send_response)

        # Define the edges of the graph
        self.state_graph.add_edge("n_identify_user", "n_identify_intent")
        self.state_graph.add_edge("n_identify_intent", "n_choose_action")
        self.state_graph.add_edge("n_choose_action", "n_act")
        self.state_graph.add_edge("n_act", "n_gen_response")
        self.state_graph.add_edge("n_gen_response", "n_send_response")

        # Set the entry point
        self.state_graph.set_entry_point("n_identify_user")

        # Compile the graph
        graph = self.state_graph.compile()
        return graph
    
    def get_conversation_state(self, phone_number: str) -> BotState:
        """Get the existing state for a conversation from DynamoDB or create a new one."""
        # Load existing state from DynamoDB
        existing_state = database.load_state(phone_number)
        
        if existing_state:
            # Check if context is expired (default 1440 minutes / 1 day)
            if database.is_context_expired(existing_state["updated_at_utc"]):
                # If expired, create new state
                return self.create_new_state(phone_number)
            return existing_state
        
        # If no existing state, create new one
        return self.create_new_state(phone_number)
    
    def create_new_state(self, phone_number: str) -> BotState:
        """Create a new state for a conversation."""
        new_state = {
            "input_msg": "",
            "context": [],
            "is_boss": False,
            "greeted": False,
            "user_id": phone_number,  # Use phone number as user_id
            "user_email": "",
            "username": "",
            "user_intent": "none",
            "chosen_action": "greet",
            "action_input": {},
            "action_result": {},
            "response": "",
            "updated_at_utc": datetime.now().isoformat()
        }
        # Save the new state to DynamoDB
        database.save_state(phone_number, new_state)
        return new_state
        
    def process_webhook_message(self, phone_number: str, message_text: str) -> str:
        # Get existing state or create new one from DynamoDB
        self.state = self.get_conversation_state(phone_number)
        
        # Update the state with new message
        self.state["input_msg"] = message_text
        self.state["updated_at_utc"] = datetime.now().isoformat()
        
        # Build and run the graph
        self.build_graph()
        final_state = self.state_graph.invoke(self.state)
        
        # Save the updated state to DynamoDB
        database.save_state(phone_number, final_state)
        
        return final_state["response"]
    
    # Method to handle the conversation
    def run(self):
        
        user_id = "teste"
        #current_context: List[ChatMessage] = []
        # save the entire state??
        result = database.load_state(user_id)

        if not result:
            current_context: List[ChatMessage] = []
            result = {
                "input_msg": "",
                "context": current_context,
                "is_boss": False,
                "greeted": False,
                "user_id": user_id,
                "user_email": "",
                "username": "",
                "user_intent": "none",
                "chosen_action": "take_intent",
                "action_input": {
                    "event_id": "",
                    "event_name": "",
                    "start_time": "",
                    "end_time": "",
                    "description": "",
                    "invited_people": [],
                    "location": "",
                    "is_update": False
                },
                "action_result": {
                    "success": False,
                    "info": ""
                },
                "response": "",
                "updated_at_utc": datetime.utcnow().isoformat()
            }

        graph = self.build_graph()

        while True:
            user_input = input("You: ")
            if user_input.lower() in {"exit", "quit"}:
                break
            current_context.append({"role": "user", "content": user_input})

            result = graph.invoke({
                **result,
                "input_msg": user_input,
                "context": current_context,
                "chosen_action": "",
                "action_result": {
                    "success": False,
                    "info": ""
                },
                "response": "",
                "updated_at_utc": datetime.utcnow().isoformat()
            })
            self.state = result
            database.save_state(user_id, result)


# ----- Run the terminal loop -----

if __name__ == "__main__":

# Initialize the state with appropriate values
    initial_state = BotState(
    input_msg="",
    context=[],  # Start with an empty context
    is_boss=False,
    greeted=False,
    user_id="",
    user_email="",
    username="",
    user_intent="",
    chosen_action="", 
    action_input=ActionInput(
        event_id="",
        event_name="",
        start_time="",
        end_time="",
        description="",
        invited_people=[],
        location="",
        is_update=False
    ),
    action_result=ActionResult(success=False, info=""),
    response="",
    updated_at_utc=""
    )

# Instantiate the Bot with the initial state
    bot = Bot(state=initial_state)

# Start the bot's run method (this will enter the input loop)
    bot.run()

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
# Possible values of user_intent: schedule, list, cancel, update, none
# Possible actions: greet, take_intent, request_more_info, follow_up (suggest)
# Possible responses: greeting, action_result, info_request, follow_up 
