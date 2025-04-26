from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import pickle
from datetime import datetime, timedelta
import pytz

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Get an authorized Google Calendar API service instance."""
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

    return build('calendar', 'v3', credentials=creds)

def list_events(time_min=None, time_max=None):
    """List events in the calendar."""
    service = get_calendar_service()
    
    # If no time range is specified, default to next 7 days
    if not time_min:
        time_min = datetime.now(pytz.UTC).isoformat()
    if not time_max:
        time_max = (datetime.now(pytz.UTC) + timedelta(days=7)).isoformat()
    
    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])

def check_availability(start_time, end_time):
    """
    Check if a time slot is available by checking for any overlapping events.
    
    Args:
        start_time (datetime): Start time of the proposed event
        end_time (datetime): End time of the proposed event
        
    Returns:
        bool: True if the time slot is available, False otherwise
    """
    try:
        # Get events that might overlap with our time slot
        # We need to check a bit before and after to catch events that might overlap
        buffer_time = timedelta(minutes=5)  # 5-minute buffer
        events = list_events(
            time_min=(start_time - buffer_time).isoformat(),
            time_max=(end_time + buffer_time).isoformat()
        )
        
        # If no events found, the slot is available
        if not events:
            return True
            
        # Check each event for overlap
        for event in events:
            event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            event_end = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))
            
            # Check if there's any overlap
            if (start_time < event_end and end_time > event_start):
                return False
                
        return True
        
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        return False  # If there's an error, assume the slot is not available

def create_event(title, start_time, end_time):
    """Create a new calendar event."""
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
    
    return service.events().insert(calendarId='primary', body=event).execute()

def cancel_event(event_id):
    """Cancel a calendar event."""
    service = get_calendar_service()
    return service.events().delete(calendarId='primary', eventId=event_id).execute()

def get_conflicting_event(start_time, end_time):
    """
    Get the details of any event that conflicts with the given time slot.
    
    Args:
        start_time (datetime): Start time of the proposed event
        end_time (datetime): End time of the proposed event
        
    Returns:
        dict: The conflicting event details if found, None otherwise
    """
    try:
        # Get all events in the time range
        events = list_events(
            time_min=start_time.isoformat(),
            time_max=end_time.isoformat()
        )
        
        # If there are any events in this time range, return the first one
        if events:
            return events[0]
        return None
        
    except Exception as e:
        print(f"Error getting conflicting event: {str(e)}")
        return None 
    

if __name__ == "__main__":
    timezone = pytz.timezone('America/Sao_Paulo')
    # Today at 18:00 in São Paulo time
    now = datetime.now(timezone)
    start_time = timezone.localize(datetime(now.year, now.month, now.day, 15, 0))
    end_time = start_time + timedelta(hours=1)
    print(check_availability(start_time, end_time))