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

def create_event(title, start_time, end_time, description=None):
    """Creates a calendar event."""
    service = get_calendar_service()
    
    event = {
        'summary': title,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
    }
    
    if description:
        event['description'] = description
    
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event

def cancel_event(event_id):
    """Cancels a calendar event."""
    service = get_calendar_service()
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True

def list_events(time_min=None, time_max=None, max_results=10, include_past=False):
    """
    Lists calendar events.
    
    Args:
        time_min (str or datetime, optional): The start time
        time_max (str or datetime, optional): The end time
        max_results (int, optional): The maximum number of events to return
        include_past (bool, optional): Whether to include past events (up to 30 days ago)
        
    Returns:
        list: A list of events
    """
    service = get_calendar_service()
    
    # Ensure time_min and time_max are properly formatted
    if not time_min:
        if include_past:
            # Include events from 30 days ago
            time_min = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            # Default to now
            time_min = datetime.datetime.utcnow().astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif isinstance(time_min, str):
        # If it's a string, make sure it's in the correct format
        try:
            # Try to parse it as a datetime
            dt = datetime.datetime.fromisoformat(time_min.replace('Z', '+00:00'))
            time_min = dt.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            # If parsing fails, use the current time or 30 days ago
            if include_past:
                time_min = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                time_min = datetime.datetime.utcnow().astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    if not time_max:
        # Default to 7 days from now
        time_max = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif isinstance(time_max, str):
        # If it's a string, make sure it's in the correct format
        try:
            # Try to parse it as a datetime
            dt = datetime.datetime.fromisoformat(time_max.replace('Z', '+00:00'))
            time_max = dt.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            # If parsing fails, use 7 days from now
            time_max = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    print(f"Listing events for time range: {time_min} to {time_max}")
    
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events
    except Exception as e:
        print(f"Error listing events: {str(e)}")
        # Return an empty list instead of raising an exception
        return []

def check_availability(start_time, end_time):
    """Checks if a time slot is available."""
    try:
        service = get_calendar_service()
        
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
        return len(events) == 0
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        # If there's an error, assume the slot is not available
        return False 