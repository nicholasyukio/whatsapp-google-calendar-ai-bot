from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import os
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
import bot.calendar.google_calendar as calendar_utils

load_dotenv()

# Define expected fields
response_schemas = [
    ResponseSchema(name="action", description="Type of action: create_event, cancel_event, list_events"),
    ResponseSchema(name="title", description="Event title"),
    ResponseSchema(name="reply", description="Bot reply"),
    ResponseSchema(name="datetime", description="Full datetime in ISO format (YYYY-MM-DDTHH:MM), or just date if not available"),
]

parser = StructuredOutputParser.from_response_schemas(response_schemas)

def identify_user(user_input: str, model):
    schema = [
    ResponseSchema(name="username", description="Personal name of the user who sent the message."),
    ]
    this_parser = StructuredOutputParser.from_response_schemas(schema)
    system_prompt = f"""
    Extract any personal information from the message below.
    Return only what is explicitly mentioned in the message.
    {parser.get_format_instructions()}
    """
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        HumanMessage(content="{input}")
    ])
    formatted_prompt = prompt.format(input=user_input)
    try:
        response = model.invoke(formatted_prompt)
        parsed = this_parser.parse(response.content)
    except Exception as e:
        print("Parsing failed:", e)
        parsed = {}
    # Fallbacks
    name = parsed.get("username", "unknown")
    return {"name": name}

class CalendarAssistant:
    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4", temperature=0)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that extracts structured information from calendar-related user input. Use the conversation history to provide context-aware responses. For timing purposes, the current date and time is {current_datetime}. You can answer with relative dates, like 'yesterday', 'today', tomorrow', 'next Monday' or 'next week', but you should also provide the exact date and time in ISO format."),
            ("human", "Previous conversation:\n{chat_history}\n\nCurrent message: {input}\n\n{format_instructions}")
        ])
        self.message_history = []
        
    def _format_chat_history(self):
        """Format the chat history for inclusion in the prompt"""
        formatted_history = ""
        for i, message in enumerate(self.message_history):
            role = "User" if isinstance(message, HumanMessage) else "Assistant"
            formatted_history += f"{role}: {message.content}\n"
        return formatted_history
    
    def _parse_datetime(self, datetime_str):
        """Parse datetime string to datetime object"""
        try:
            # Try to parse ISO format
            return datetime.fromisoformat(datetime_str)
        except ValueError:
            # If not ISO format, try to extract date and time using regex
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', datetime_str)
            time_match = re.search(r'(\d{2}:\d{2})', datetime_str)
            
            if date_match and time_match:
                date_str = date_match.group(1)
                time_str = time_match.group(1)
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            elif date_match:
                date_str = date_match.group(1)
                return datetime.strptime(date_str, "%Y-%m-%d")
            else:
                return None
        
    def _process_calendar_action(self, result, phone_number):
        """Process calendar actions based on the AI interpretation"""
        action = result.get('action', '')
        title = result.get('title', '')
        datetime_str = result.get('datetime', '')
        
        if not datetime_str:
            return result
        
        # Parse datetime
        event_datetime = self._parse_datetime(datetime_str)
        if not event_datetime:
            result['reply'] = "I couldn't understand the date and time you provided. Could you please specify it again?"
            return result
        
        # Default event duration is 1 hour
        event_end = event_datetime + timedelta(hours=1)
        
        if action == 'create_event':
            # Check if the time slot is available
            try:
                is_available = calendar_utils.check_availability(event_datetime, event_end)
                if is_available:
                    try:
                        event = calendar_utils.create_event(title, event_datetime, event_end)
                        result['reply'] = f"Event '{title}' has been scheduled for {event_datetime.strftime('%Y-%m-%d %H:%M')}."
                    except Exception as e:
                        print(f"Error creating event: {str(e)}")
                        result['reply'] = "I'm having trouble understanding your request. Could you please try again?"
                else:
                    # Get the conflicting event details
                    conflicting_event = calendar_utils.get_conflicting_event(event_datetime, event_end)
                    if conflicting_event:
                        if phone_number == "5512981586001":
                            # For the boss, offer to cancel the conflicting event
                            result['reply'] = f"The time slot {event_datetime.strftime('%Y-%m-%d %H:%M')} is not available. There is an existing event: '{conflicting_event.get('summary', 'Untitled')}' from {conflicting_event.get('start', {}).get('dateTime', 'unknown time')} to {conflicting_event.get('end', {}).get('dateTime', 'unknown time')}. Would you like me to cancel this event and schedule your new event instead?"
                            # Store the conflicting event ID in the result for potential cancellation
                            result['conflicting_event_id'] = conflicting_event.get('id')
                        else:
                            # For other users, just inform that the slot is not available
                            result['reply'] = f"I'm sorry, but the time slot {event_datetime.strftime('%Y-%m-%d %H:%M')} is not available. Please choose another time."
            except Exception as e:
                print(f"Error checking availability: {str(e)}")
                result['reply'] = "I'm having trouble understanding your request. Could you please try again?"
        
        elif action == 'cancel_event':
            # For cancel_event, we need to find the event by title and date
            try:
                events = calendar_utils.list_events(
                    time_min=event_datetime.isoformat(),
                    time_max=(event_datetime + timedelta(days=1)).isoformat()
                )
                
                # Find the event with matching title
                event_to_cancel = None
                for event in events:
                    if event.get('summary', '').lower() == title.lower():
                        event_to_cancel = event
                        break
                
                if event_to_cancel:
                    try:
                        calendar_utils.cancel_event(event_to_cancel['id'])
                        result['reply'] = f"Event '{title}' has been cancelled."
                    except Exception as e:
                        print(f"Error cancelling event: {str(e)}")
                        result['reply'] = "I'm having trouble understanding your request. Could you please try again?"
                else:
                    result['reply'] = f"I couldn't find an event titled '{title}' on {event_datetime.strftime('%Y-%m-%d')}. Could you please check the title and try again?"
            except Exception as e:
                print(f"Error listing events for cancellation: {str(e)}")
                result['reply'] = "I'm having trouble understanding your request. Could you please try again?"
        
        elif action == 'list_events':
            # List events for the specified date
            try:
                events = calendar_utils.list_events(
                    time_min=event_datetime.isoformat(),
                    time_max=(event_datetime + timedelta(days=1)).isoformat()
                )
                
                if events:
                    event_list = "\n".join([f"- {event.get('summary')}: {event.get('start', {}).get('dateTime', 'No time')}" for event in events])
                    result['reply'] = f"Events on {event_datetime.strftime('%Y-%m-%d')}:\n{event_list}"
                else:
                    result['reply'] = f"No events found for {event_datetime.strftime('%Y-%m-%d')}."
            except Exception as e:
                print(f"Error listing events: {str(e)}")
                result['reply'] = "I'm having trouble understanding your request. Could you please try again?"
        
        return result
        
    def interpret_user_input(self, user_input: str, phone_number: str = None):
        # Add the user message to history
        self.message_history.append(HumanMessage(content=user_input))
        
        # Get current datetime
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Select prompt based on phone number
        if phone_number == "5512981586001":
            system_prompt = """
You are a helpful secretary assistant whose job is to manage the calendar of a busy person (your 'boss').
             
Therefore, you should be able to extract structured information from calendar-related user input and help the user schedule events.
             
The user is your 'boss', so you have full access to all calendar functions and can see all events.
             
# Tone and language
- Be friendly, polite and professional
- Speak in the style of a secretary
- Answer in the same language as the user
- If you send messages in a language that is not gender-specific, make sure to use the feminine form.

# Timing and dates standards
For timing purposes, the current date and time is {current_datetime}.
             
You can answer with relative dates, like 'yesterday', 'today', 'tomorrow', 'next Monday' or 'next week',
but you should also provide the exact date and time hh:mm, dd:mm:yyyy format.
             
Your boss timezone is UTC-3, so if someone else outside of UTC-3 schedules an event, you should ask for the date and time in the UTC-3 timezone.

# Time table conflict
Before scheduling an event, check if the time slot is available. If it is not available, tell the event that is scheduled and ask if the boss wants to cancel it and schedule a new one.

# Procedure
When scheduling events, extract the following information:
- Event title or summary
- Start date and time
- End date and time
- Location (if provided)
- Description (if provided)

# Final notes
When listing events, check if the user wants past events or just upcoming events.
             
You can see all events in the calendar, regardless of who created them.
             
You must use follow up questions or statements, like asking if there is something else you can do for them, or in the case that the user already told that they are statisfied and do not need anything else, you can inform that you are at their service.

# Greeting
To greet your boss, always say "Hello, boss" or a similar respectful greeting.
"""
        else:
            system_prompt = """
You are a helpful secretary assistant whose job is to manage the calendar of a busy person (your 'boss').
             
Therefore, you should be able to extract structured information from calendar-related user input and help the user schedule events.
             
The user is someone else who wants to schedule events on your boss's calendar, so you have limited access to calendar functions.
             
# Tone and language
- Be friendly, polite and professional
- Speak in the style of a secretary
- Answer in the same language as the user
- If you send messages in a language that is not gender-specific, make sure to use the feminine form.

# Timing and dates standards
For timing purposes, the current date and time is {current_datetime}.
             
You can answer with relative dates, like 'yesterday', 'today', 'tomorrow', 'next Monday' or 'next week',
but you should also provide the exact date and time hh:mm, dd:mm:yyyy format.
             
Your boss timezone is UTC-3, so if someone else outside of UTC-3 schedules an event, you should ask for the date and time in the UTC-3 timezone.

# Time table conflict
Before scheduling an event, check if the time slot is available. If it is not available, ask the user to choose another time.

# Procedure
When scheduling events, extract the following information:
- Event title or summary
- Start date and time
- End date and time
- Location (if provided)
- Description (if provided)

# Final notes
When listing events, check if the user wants past events or just upcoming events.
             
If a user that is not your boss wants to schedule an event on your boss's calendar, you can tell them that certain time slots are not available, but you cannot reveal which your boss is taking part in. In this case, you could only reveal events that were scheduled by the same user. This means that, for instance, if user1 asks for events your boss is taking part in, you could only reveal events scheduled by user1.
             
You must use follow up questions or statements, like asking if there is something else you can do for them, or in the case that the user already told that they are statisfied and do not need anything else, you can inform that you are at their service.

# Greeting
To greet users, always ask "Hello, what is your name?" or a similar friendly greeting.
"""
        
        # Create prompt with selected system message
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Previous conversation:\n{chat_history}\n\nCurrent message: {input}\n\n{format_instructions}")
        ])
        
        # Format the prompt with the user input, chat history, and format instructions
        formatted_prompt = prompt.format(
            input=user_input,
            chat_history=self._format_chat_history(),
            format_instructions=parser.get_format_instructions(),
            current_datetime=current_datetime
        )
        
        # Get response from the model
        response = self.model.invoke(formatted_prompt)
        
        # Parse the structured output
        parsed_response = parser.parse(response.content)
        
        # Process calendar actions
        processed_response = self._process_calendar_action(parsed_response, phone_number)
        
        # Add the AI response to history
        self.message_history.append(AIMessage(content=response.content))
        
        return processed_response
    
    def interpret_user_input(self, user_input: str, phone_number: str = None):
        # Add the user message to history
        self.message_history.append(HumanMessage(content=user_input))
        # Get current datetime
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = """
        Extract the user personal information from the message below.
        """
        # Create prompt with selected system message
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", input)
        ])
        # Format the prompt with the user input, chat history, and format instructions
        formatted_prompt = prompt.format(
            input=user_input,
            chat_history=self._format_chat_history(),
            format_instructions=parser.get_format_instructions(),
            current_datetime=current_datetime
        )
        # Get response from the model
        response = self.model.invoke(formatted_prompt)
        # Parse the structured output
        parsed_response = parser.parse(response.content)
        # Process calendar actions
        processed_response = self._process_calendar_action(parsed_response, phone_number)
        # Add the AI response to history
        self.message_history.append(AIMessage(content=response.content))
        return processed_response


# Create a singleton instance
calendar_assistant = CalendarAssistant()

# Function to be used by other parts of the application
def interpret_user_input(user_input: str, phone_number: str = None):
    return calendar_assistant.interpret_user_input(user_input, phone_number)
