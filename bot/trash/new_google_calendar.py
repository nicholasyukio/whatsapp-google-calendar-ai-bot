import os
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
from google_calendar import (
    get_calendar_service,
    create_event as google_create_event,
    cancel_event as google_cancel_event,
    list_events as google_list_events,
    check_availability as google_check_availability,
    update_event as update_event
)

# Load environment variables
load_dotenv()

service = get_calendar_service()

def create_event(summary, start_time, end_time, description=None, location=None):
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
        # Convert string times to datetime objects if needed
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
        
        # Create the event
        event = google_create_event(
            title=summary,
            start_time=start_time,
            end_time=end_time,
            description=description
        )
        
        # Add location if provided
        if location:
            event['location'] = location
            # Update the event with the location
            service.events().update(
                calendarId='primary',
                eventId=event['id'],
                body=event
            ).execute()
        
        print(f"Event created: {summary}")
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
        result = google_cancel_event(event_id)
        print(f"Event cancelled: {event_id}")
        return result
        
    except Exception as e:
        print(f"Error cancelling event: {str(e)}")
        raise

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
        try:
            # Ensure time_min and time_max are properly formatted
            if time_min and isinstance(time_min, str):
                try:
                    # Try to parse it as a datetime
                    time_min = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
                except ValueError:
                    # If parsing fails, use None (will use default in google_calendar.py)
                    time_min = None
                
            if time_max and isinstance(time_max, str):
                try:
                    # Try to parse it as a datetime
                    time_max = datetime.fromisoformat(time_max.replace('Z', '+00:00'))
                except ValueError:
                    # If parsing fails, use None (will use default in google_calendar.py)
                    time_max = None
            
            events = google_list_events(
                time_min=time_min,
                time_max=time_max,
                max_results=max_results,
                include_past=include_past
            )
            print(f"Retrieved {len(events)} events")
            print("Events: ", events)
            return events
            
        except Exception as e:
            print(f"Error listing events: {str(e)}")
            # Return an empty list instead of raising an exception
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
        # Convert string times to datetime objects if needed
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
        
        is_available = google_check_availability(start_time, end_time)
        print(f"Availability check: {is_available}")
        return is_available
        
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        raise 

if __name__ == "__main__":
    std_datetime = datetime.now()
    std_datetime_iso = std_datetime.isoformat()
    std_datetime_1_hour_later = std_datetime + timedelta(hours=1)
    std_datetime_1_hour_later_iso = std_datetime_1_hour_later.isoformat()
    std_datetime_7_days_later = std_datetime + timedelta(days=7)
    std_datetime_7_days_later_iso = std_datetime_7_days_later.isoformat()

    std_datetime_2_iso = "2025-04-29T17:00:00.000000"
    std_datetime_2_iso_1_hour_later = "2025-04-29T18:00:00.000000"
    #create_event("Test", std_datetime_iso, std_datetime_1_hour_later_iso, "Event description", "São Paulo")
    #create_event("Test 3", std_datetime_2_iso, std_datetime_2_iso_1_hour_later, "Event description", "London")
    #check_availability(std_datetime_2_iso, std_datetime_2_iso_1_hour_later)
    #list_events()
    #cancel_event("kj66cj4lbev0p33pr0k0p8jnmo")
    std_datetime_2_iso_obj = datetime.fromisoformat(std_datetime_2_iso)
    std_datetime_2_iso_1_hour_later_obj = datetime.fromisoformat(std_datetime_2_iso_1_hour_later)
    update_event("qv186s3h8b19fkelf9vaufu3gg", start_time=std_datetime_2_iso_obj, end_time=std_datetime_2_iso_1_hour_later_obj)