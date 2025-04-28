import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from dotenv import load_dotenv

load_dotenv()

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Gets an authorized Google Calendar API service instance."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

def create_event(summary, start_time, end_time, description=None, location=None, attendees_emails=None):
    """
    Create a new calendar event.
    
    Args:
        summary (str): The title of the event
        start_time (str): The start time in ISO format (YYYY-MM-DDTHH:MM:SS)
        end_time (str): The end time in ISO format (YYYY-MM-DDTHH:MM:SS)
        description (str, optional): A description of the event
        location (str, optional): The location of the event
        
    Returns:
        dict: The created event
    """
    try:
        service = get_calendar_service()
        # Convert string times to datetime objects if needed
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.datetime.fromisoformat(end_time)
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meet-{datetime.datetime.now().timestamp()}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            },
            **({'description': description} if description else {}),
            **({'location': location} if location else {}),
            **({'attendees': [{'email': email} for email in attendees_emails]} if attendees_emails else {}),
        }

        event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1  # <- important for Meet link!
        ).execute()
        print(event)
        return event
    except Exception as e:
        print(f"Error creating event: {str(e)}")
        raise

def cancel_event(event_id):
    """
    Cancel a calendar event.
    
    Args:
        event_id (str): The ID of the event to cancel
        
    Returns:
        bool: True if the event was cancelled successfully
    """
    try:
        service = get_calendar_service()
        result = service.events().delete(calendarId='primary', eventId=event_id).execute()
        print(f"Event cancelled: {event_id}, with result: {result}")
        return True
        
    except Exception as e:
        print(f"Error cancelling event: {str(e)}")
        return False

def list_events(time_min=None, time_max=None, max_results=10, include_past=False):
    """
    List calendar events.

    Args:
        time_min (str, optional): The start time in ISO format (YYYY-MM-DDTHH:MM:SS)
        time_max (str, optional): The end time in ISO format (YYYY-MM-DDTHH:MM:SS)
        max_results (int, optional): The maximum number of events to return
        include_past (bool, optional): Whether to include past events (up to 30 days ago)

    Returns:
        list: A list of events
    """
    def prepare_time(value, default_days_offset):
        if value and isinstance(value, str):
            try:
                value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                value = None
        if not value:
            value = datetime.datetime.utcnow() + datetime.timedelta(days=default_days_offset)
        return value.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    try:
        service = get_calendar_service()

        time_min_formatted = prepare_time(time_min, -30 if include_past else 0)
        time_max_formatted = prepare_time(time_max, 7)

        print(f"Listing events for time range: {time_min_formatted} to {time_max_formatted}")

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min_formatted,
            timeMax=time_max_formatted,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        print(f"Retrieved {len(events)} events")
        print("Events:", events)
        return events

    except Exception as e:
        print(f"Error listing events: {str(e)}")
        return []

def check_availability(start_time, end_time):
    """
    Check if a time slot is available.
    
    Args:
        start_time (str): The start time in ISO format (YYYY-MM-DDTHH:MM:SS)
        end_time (str): The end time in ISO format (YYYY-MM-DDTHH:MM:SS)
        
    Returns:
        bool: True if the time slot is available, False otherwise
    """
    try:
        service = get_calendar_service()
        # Convert string times to datetime objects if needed
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.datetime.fromisoformat(end_time)
        # Format times for the API - use UTC format with 'Z' suffix
        # This is the format that Google Calendar API expects
        time_min = start_time.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        time_max = end_time.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        print(f"Checking availability for time range: {time_min} to {time_max}")
        # Get events in the time range
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        # If there are no events, the time slot is available
        is_available = len(events) == 0
        print(f"Availability check: {is_available}")
        return is_available
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        raise 
    
def update_event(event_id, title=None, start_time=None, end_time=None, description=None, location=None, attendees_emails=None):
    """Updates an existing calendar event."""
    service = get_calendar_service()
    # First, get the existing event
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    # Update fields only if new values are provided
    if title:
        event['summary'] = title
    if description:
        event['description'] = description
    if location:
        event['location'] = location
    if attendees_emails:
        event['attendees'] = [{'email': email} for email in attendees_emails]
    if start_time:
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time)
        event['start'] = {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        }
    if end_time:
        if isinstance(end_time, str):
            end_time = datetime.datetime.fromisoformat(end_time)
        event['end'] = {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        }

    # Push the updated event
    updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    return updated_event

if __name__ == "__main__":
    std_datetime = datetime.datetime.now()
    std_datetime_iso = std_datetime.isoformat()
    std_datetime_1_hour_later = std_datetime + datetime.timedelta(hours=1)
    std_datetime_1_hour_later_iso = std_datetime_1_hour_later.isoformat()
    std_datetime_7_days_later = std_datetime + datetime.timedelta(days=7)
    std_datetime_7_days_later_iso = std_datetime_7_days_later.isoformat()

    std_datetime_2_iso = "2025-04-29T20:00:00.000000"
    std_datetime_2_iso_1_hour_later = "2025-04-29T21:00:00.000000"
    #create_event("Test4", std_datetime_2_iso, std_datetime_2_iso_1_hour_later, "Event description", "São José dos Campos")
    #create_event("Test 3", std_datetime_2_iso, std_datetime_2_iso_1_hour_later, "Event description", "London")
    #check_availability(std_datetime_2_iso, std_datetime_2_iso_1_hour_later)
    #list_events(max_results=4, include_past=False)
    #cancel_event("kj66cj4lbev0p33pr0k0p8jnmo")
    #std_datetime_2_iso_obj = datetime.fromisoformat(std_datetime_2_iso)
    #std_datetime_2_iso_1_hour_later_obj = datetime.fromisoformat(std_datetime_2_iso_1_hour_later)
    update_event("g3b0o1govcs2b13ddufu9cpu6s", start_time=std_datetime_2_iso, end_time=std_datetime_2_iso_1_hour_later, attendees_emails=["salve@salveregina.com.br"])
    # create_event(
    # summary="Project Meeting",
    # start_time="2025-04-27T10:00:00",
    # end_time="2025-04-27T11:00:00",
    # description="Discussion about the project deliverables.",
    # location="Online",
    # attendees_emails=["nicholasyukio@canaldoeletron.com.br", "salve@salveregina.com.br"]
    # )
