from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from bot.lang2.mytypes import ActionResult, UpdateData, CancelData, ScheduleData
import bot.lang2.google_calendar as google_calendar
from bot.lang2.llm import LLM
import os

is_local = os.path.exists('.env')

if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

BOSS_NAME = os.getenv("BOSS_NAME")

blocked_times = {
    "weekdays": [
        (time(0, 0), time(7, 59)),
        (time(20, 0), time(23, 59)),
    ],
    "weekends": "all",
}

llm = LLM()

# Google Calendar Part

# Function to handle scheduling a meeting
def schedule_meeting(data: ScheduleData, email: str, username: str) -> ActionResult:
    event_name = data.get("event_name")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    description = data.get("description")
    invited_people = data.get("invited_people", []) + [email]
    location = data.get("location", "")
    google_meet_link = ""

    avail = is_time_slot_available(start_time, end_time)

    if email == "":
        result = {
            "success": False,
            "info": "FAIL:SCHEDULE: email address is needed to schedule a meeting"
        }
        return result

    if event_name == "unknown":
        event_name = f"{username} <> {BOSS_NAME}"

    if description == "unknown":
        description = "Event scheduled by CAIB (Calendar Artificial Intelligence Bot)"

    if avail == "available":
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
            "info": f"SUCCESS:SCHEDULE: The meeting '{event_name}' scheduled from {start_time} to {end_time}. "
                    f"Participants: {', '.join(invited_people)}. Event description: {description}, "
                    f"Location: {location}. Google Meet link: {google_meet_link}"
        }
    else:
        info_start = f"""FAIL:SCHEDULE: The meeting '{event_name}' scheduled from {start_time} to {end_time}. "
                        Participants: {', '.join(invited_people)}. Event description: {description}, "
                        Location: {location}. Google Meet link: {google_meet_link}"""
        if avail == "time_reverted":
            info_end = "Reason: start time cannot be later than end time"
        elif avail == "time_not_provided":
            info_end = "Reason: start and end time of the event must be provided"
            suggestions_rst = suggest_time_slots()
            if suggestions_rst["success"]:
                suggestions_rst_str = suggestions_rst["info"]
                info_end = f"{info_end}\n{suggestions_rst_str}"
        elif avail == "rest_time":
            info_end = "Reason: this time is blocked because it is in the boss' rest time"
            suggestions_rst = suggest_time_slots()
            if suggestions_rst["success"]:
                suggestions_rst_str = suggestions_rst["info"]
                info_end = f"{info_end}\n{suggestions_rst_str}"
        elif avail == "already_busy":
            info_end = "Reason: the time slot is already occupied"
            suggestions_rst = suggest_time_slots()
            if suggestions_rst["success"]:
                suggestions_rst_str = suggestions_rst["info"]
                info_end = f"{info_end}\n{suggestions_rst_str}"
        else:
            info_end = "Reason: unknown"
        result = {
            "success": False,
            "info": f"{info_start}\n{info_end}"
        }
    
    return result

def cancel_meeting(data: CancelData) -> ActionResult:
    """
    Cancels a meeting based on the event name from the state.
    
    Returns:
        dict: A dictionary containing success status and information message.
    """

    event_id = data.get("event_id")
    if event_id:
        success = google_calendar.cancel_event(event_id)
        # It seems success is not returning the real status
        if success:
            info = f"SUCCESS:CANCEL: The meeting has been successfully canceled."
        else:
            info = f"FAIL:CANCEL: Failed to cancel the meeting'."
        # Update the state with the canceled meeting result
        result = {
            "success": success,
            "info": info
        }
    else:
        success = False
        info = "FAIL:CANCEL: Cancelation not possible because event was not found"
        result = {
            "success": success,
            "info": info
        }
    return result

def update_meeting(data: UpdateData, email: str) -> ActionResult:
    now = data.get("now", {})
    later = data.get("later", {})

    event_id = now.get("event_id", None)
    event_name = now.get("event_name", None)
    start_time = now.get("start_time", None)
    end_time = now.get("end_time", None)
    description = now.get("description", None)
    invited_people = now.get("invited_people", [])
    location = now.get("location", None)

    new_event_name = later.get("event_name", None)
    new_start_time = later.get("start_time", None)
    new_end_time = later.get("end_time", None)
    new_description = later.get("description", None)
    new_invited_people = later.get("invited_people", [])
    new_location = later.get("location", None)

    if new_event_name == "the_same":
        new_event_name = None
    if new_start_time == "the_same":
        new_start_time = None
    if new_end_time == "the_same":
        new_end_time = None
    if new_description == "the_same":
        new_description = None
    if new_location == "the_same":
        new_location = None

    if new_invited_people == invited_people:
        attendees_emails = None
    else:
        if email not in new_invited_people:
            new_invited_people.append(email)
        attendees_emails = new_invited_people

    if all(not val for val in (
    new_event_name,
    new_start_time,
    new_end_time,
    new_description,
    new_location,
    new_invited_people
    )):
        print("All values are None or empty.")
        result = {
            "success": False,
            "info": "FAIL:UPDATE: No new value to update in meeting"
        }
        return result

    if not new_start_time and not new_end_time:
        avail = "available"
    if new_start_time and not new_end_time:
        avail = is_time_slot_available(new_start_time, end_time, event_id)
    if not new_start_time and new_end_time:
        avail = is_time_slot_available(start_time, new_end_time, event_id)
    if new_start_time and new_end_time:
        avail = is_time_slot_available(new_start_time, new_end_time, event_id)
    
    info_start = f"FAIL:UPDATE: "
    info_end = ""
    if avail == "time_reverted":
        info_end = "Failure reason: start time cannot be later than end time"
    elif avail == "rest_time":
        info_end = "Failure reason: this time is blocked because it is in the boss' rest time"
        suggestions_rst = suggest_time_slots()
        if suggestions_rst["success"]:
            suggestions_rst_str = suggestions_rst["info"]
            info_end = f"{info_end}\n{suggestions_rst_str}"
    elif avail == "already_busy":
        info_end = "Failure reason: the time slot is already occupied"
        if suggestions_rst["success"]:
            suggestions_rst_str = suggestions_rst["info"]
            info_end = f"{info_end}\n{suggestions_rst_str}"
    result = {
        "success": False,
        "info": f"{info_start}\n{info_end}"
    }
    if avail != "available" and avail != "same_event":
        return result
        
    if event_id:
        try:
            gresult = google_calendar.update_event(
                    event_id=event_id,
                    title=new_event_name,
                    start_time=new_start_time,
                    end_time=new_end_time,
                    description=new_description,
                    location=new_location,
                    attendees_emails=attendees_emails
            )
            success = (gresult["status"] == "confirmed")
            info = f"""SUCCESS:UPDATE: The meeting '{event_name}' has been updated successfully. 
            New details: Start: {start_time}, End: {end_time}, 
            Description: {description}, Location: {location},
            Participants: {', '.join(attendees_emails)}"""
        except Exception as e:
            success = False
            info = f"FAIL:UPDATE: Failed to update the meeting '{event_name}' in Google Calendar."
    else:
        success = False
        info = "FAIL:UPDATE: Failed to find the meeting to update in Google Calendar"
    # Return the result
    result = {
        "success": success,
        "info": info
    }
    return result

# Auxiliary Google Calendar functions

def is_time_slot_available(start_time_str: str, end_time_str: str, event_id: str = None) -> str:
    if not start_time_str or not end_time_str:
        return "time_not_provided"
    
    if start_time_str == "unknown" or end_time_str == "unknown":
        return "time_not_provided"
    
    if start_time_str == "the_same" or end_time_str == "the_same":
        return "same_event"

    start_time = datetime.fromisoformat(start_time_str)
    end_time = datetime.fromisoformat(end_time_str)

    if start_time > end_time:
        return "time_reverted"

    # 1. Check if time is blocked
    current = start_time
    while current < end_time:
        if is_time_blocked(current):
            return "rest_time"
        current += timedelta(minutes=1)

    # 2. Check for overlap with busy events
    events = google_calendar.list_events(
        time_min=start_time_str,
        time_max=end_time_str,
        max_results=100,
        include_past=False
    )

    for event in events:
        this_event_id = event.get('id')
        if event_id:
            if event_id == this_event_id:
                return "same_event"
        event_start = datetime.fromisoformat(event['start']['dateTime'])
        event_end = datetime.fromisoformat(event['end']['dateTime'])

        # Check if the input time overlaps with any busy event
        if not (end_time <= event_start or start_time >= event_end):
            return "already_busy"

    return "available"

def suggest_time_slots(start_time_str: str = None, end_time_str: str = None, slot_duration_minutes: int = 60) -> ActionResult:
    
    if start_time_str and end_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
    else:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        start_time = datetime.combine(now.date(), time(8, 0), tzinfo=ZoneInfo("America/Sao_Paulo"))
        end_time = start_time + timedelta(days=7)
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

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
        blocked = is_time_blocked(current_time)

        if not overlapping and not blocked:
            suggestions.append(f"{current_time.strftime('%Y-%m-%d %H:%M')} to {slot_end_time.strftime('%H:%M')}")

        current_time += timedelta(minutes=slot_duration_minutes)

    if not suggestions:
        success = False
        info = "No available time slots found."
    else:
        success = True
        info = "AVAILABLE TIME SLOT SUGGESTIONS:\n" + "\n".join(suggestions)

    return {
        "success": success,
        "info": info
    }

def list_meetings(email, is_boss, start_time_str: str = None, end_time_str: str = None, include_past: bool = True) -> ActionResult:
    if not start_time_str and not end_time_str:
        start_time = datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=30)
        end_time = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(days=90)
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()
    
    # Assuming google_calendar.list_events is an external function:
    events = google_calendar.list_events(
        time_min=start_time_str, 
        time_max=end_time_str, 
        max_results=100, 
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
            location = event.get('location', 'online')
            description = event.get('description', 'unknown')
            attendees_email_list = [attendee.get('email', 'Unknown') for attendee in attendees]
            if email in attendees_email_list or is_boss:
                participants = ", ".join(attendees_email_list)
                meeting_details = f"#{k}: Id: {event_id}, Meeting: {summary}, Time: {start} to {end}, Participants: {participants}, Location: {location}, Description: {description}"
                meetings_list.append(meeting_details)
                k = k + 1
        info = "MEETINGS OF THE USER: "+"\n".join(meetings_list)+"\n\n"
    result = {
        "success": success,
        "info": info
    }
    return result

def handle_unknown(data):
    result = {
            "success": True,
            "info": "UNKNOWN INTENT"
    }
    return result

    # Default blocked times
def is_time_blocked(check_time: datetime) -> bool:
    weekday = check_time.weekday()
    t = check_time.time()

    if weekday >= 5:  # Saturday=5, Sunday=6
        return blocked_times["weekends"] == "all"

    for start, end in blocked_times["weekdays"]:
        if start <= t <= end:
            return True
    return False