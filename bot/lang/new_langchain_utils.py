from openai import OpenAI
from datetime import datetime
import os
import json
from dotenv import load_dotenv

load_dotenv()

now = datetime.now().isoformat()
time_context = f"The current date and time is: {now}"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def greet_user(user_input: str, username: str, is_boss: bool):
    if is_boss:
        system_prompt = f"""
        You are a smart assistant helping your boss manage their calendar and now you have to
        greet your boss, with due respect because he is your boss. Treat him like royalty.

        End the greeting with a polite follow up question about something you might help him with.

        Your boss name is '{username}'.

        {time_context}.

        The greeting and your follow up question must match your boss message '{user_input}'
        """
    else:
        system_prompt = f"""
        You are a smart assistant helping your boss manage their calendar and now you have to
        greet an user that is somebody else who want to contact you about a meeting with your boss.

        End the greeting with a polite follow up question explaining your job and asking how can you help
        them about meetings with your boss.

        The name of the user is '{username}'.

        {time_context}.

        The greeting and your follow up question must match the user message '{user_input}'
        """
    response = client.chat.completions.create(
        model="gpt-4",
        temperature=0.7,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    content = response.choices[0].message.content.strip()
    return content

def follow_up(user_input: str, username: str, is_boss: bool):
    if is_boss:
        system_prompt = f"""
        You are a smart assistant helping your boss manage their calendar and you already completed the requested task
        about managing meetings in their calendar.

        Now you have to give a follow up question asking if there is something else you could help 
        them with, or, in the case that they already confirmed that they are satisfied, you should give a
        respectful goodbye message and say that you are at their service whenever they need you about their agenda.

        Your boss name is '{username}'.

        {time_context}.

        The last message sent by your boss is '{user_input}'.
        """
    else:
        system_prompt = f"""
        You are a smart assistant helping your boss manage their calendar and you are talking to an user about
        meetings with your boss. 

        Now you have to give a follow up question asking if there is something else you could help 
        them with, or, in the case that they already confirmed that they are satisfied, you should give a
        polite goodbye message and say that if they want anything related to meetings with your boss, they
        should feel free to contact you.

        The user name is '{username}'.

        {time_context}.

        The last message sent by the user is '{user_input}'.
        """
    response = client.chat.completions.create(
        model="gpt-4",
        temperature=0.7,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    content = response.choices[0].message.content.strip()
    return content

def identify_user(user_input: str):
    system_prompt = """
    You are a helpful assistant that extracts personal information from a message.
    Return a JSON object with this format:
    {
      "username": "<name>"
    }
    Only fill "username" with what is explicitly said in the input meaning the personal name of the user.
    If the name is not present, use "unknown".
    """
    response = client.chat.completions.create(model="gpt-4",
    temperature=0,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ])

    content = response.choices[0].message.content
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        print("Invalid JSON. Raw content:", content)
        parsed = {}
    username = parsed.get("username", "unknown")
    return {"username": username}

def identify_intent(user_input: str):
    system_prompt = """
    Extract user intention from the message.
    Return a JSON object with this format:
    {
      "intent": "<intention>"
    }
    Valid intention options: 'schedule', 'list', 'cancel', 'check', 'update', 'none'
    Unclear, non existing or invalid intents must be classified as 'none'.
    Choose only one option.
    Only fill "intent" with what is explicitly said in the input about what the user wants.
    """
    response = client.chat.completions.create(model="gpt-4",
    temperature=0,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ])

    content = response.choices[0].message.content
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        print("Invalid JSON. Raw content:", content)
        parsed = {}
    intent = parsed.get("intent", "unknown")
    return {"intent": intent}

def extract_action_input(user_input: str, context: list[str], user_intent: str):
    full_fields = {
        "event_name": "",
        "start_time": "",
        "end_time": "",
        "description": "",
        "invited_people": [],
        "meet_link": ""
    }

    if user_intent == "schedule":
        expected_fields = ["event_name", "start_time", "end_time", "description", "invited_people", "meet_link"]
        system_prompt = """
You are an assistant that extracts structured action input data from a conversation.

{time_context}.

Return a JSON object with this format:
{
  "event_name": "<name of the event>",
  "start_time": "<start time in ISO 8601 or 'unknown'>",
  "end_time": "<end time in ISO 8601 or 'unknown'>",
  "description": "<short description or 'unknown'>",
  "invited_people": ["<names or emails>"],
  "meet_link": "<link or 'unknown'>"
}

Only include information that is explicitly stated or clearly implied. Use "unknown" or empty list if unsure. Do NOT include any other fields or explanations.
"""

    elif user_intent == "list":
        expected_fields = ["start_time", "end_time"]
        system_prompt = """
You are an assistant that extracts time range information to list scheduled meetings.

{time_context}.

Return a JSON object with this format:
{
  "start_time": "<start range in ISO 8601 or 'unknown'>",
  "end_time": "<end range in ISO 8601 or 'unknown'>"
}

Only include what's explicitly stated or implied. Do NOT include any other fields or text.
"""

    elif user_intent in ["cancel", "check", "update"]:
        expected_fields = ["event_name"]
        system_prompt = f"""
You are an assistant that extracts the name of an event to {user_intent}.

{time_context}.

Return a JSON object with this format:
{{
  "event_name": "<name of the event or 'unknown'>"
}}

Only include this field. Do NOT include any other fields or text.
"""
    else:
        # For unknown/unsupported intents, return blank structure
        return full_fields

    # Monta o histórico para envio ao modelo
    history = [{"role": "system", "content": system_prompt}]
    for msg in context:
        history.append({"role": "user", "content": msg})
    history.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            temperature=0,
            messages=history
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
    except Exception as e:
        print("Error parsing:", e)
        print("Raw content:", content if 'content' in locals() else "")
        parsed = {}

    # Preenche o JSON completo com os valores retornados, deixando o resto vazio
    result = full_fields.copy()
    for field in expected_fields:
        result[field] = parsed.get(field, full_fields[field])

    return result

def generate_missing_info_request(user_input: str, intent: str, action_input: dict) -> str:
    system_prompt = f"""
You are a smart assistant helping a user manage their calendar.

The user wants to: '{intent}'.

{time_context}.

Below is the extracted data:
{json.dumps(action_input, indent=2)}

Based on the intent, check what is missing. The required information for each intent is:

- "schedule":
    - event_name (string)
    - start_time (datetime string)
    - end_time (datetime string)
    - description (optional)
    - invited_people (list of names or emails)
    - meet_link (optional)

- "list":
    - start_time (datetime string)
    - end_time (datetime string)

- "cancel":
    - event_name (string)

- "check":
    - event_name (string)

- "update":
    - event_name (string)
    - at least one of the following must be present: start_time, end_time, description, invited_people, meet_link

Your task:
1. Identify which required fields are missing.
2. Generate a short and polite message asking **only** for the missing fields.
3. Do not repeat the user's input.
4. If everything needed is already present, reply: "All set!"

Keep your message natural and conversational.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        temperature=0.7,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    print("LLM Response: ", response)
    content = response.choices[0].message.content.strip()
    return content

def generate_confirmation_response(user_input: str, intent: str, action_input: dict, action_result: str) -> str:
    if intent == "list":
        system_prompt = f"""
    You are a smart assistant helping your boss manage their calendar, who wants to know all the current meetings they have.

    {time_context}.

    The list of meeting your boss has scheduled is: '{action_result}'.

    Your task:
    1. Generate a short response listing all the meetings your boss has and asking if they want information about one of them or to modify one of them.
    2. Ensure that the time is in the "hh:mm of dd/mm/yy" format.
    """
    else:
        system_prompt = f"""
    You are a smart assistant helping a user manage their calendar.

    {time_context}.

    The user wants to: '{intent}'.

    Below is the extracted data:
    {json.dumps(action_input, indent=2)}

    Based on the intent, generate a confirmation response in natural language. The response should include:
    - A clear confirmation of the user's intent (e.g., "Your meeting has been scheduled," "Your meeting has been updated," or "Your meeting has been cancelled").
    - All the relevant details of the meeting in natural language, including the event name, start time, end time, description, invited people, and meeting link (if applicable).
    - If the meeting times are provided, convert them to the format: "hh:mm of dd/mm/yy" (e.g., "15:30 of 25/04/2025").
    - If any optional fields are missing, do not include them in the response.

    Here is the information you have:
    1. Event Name: {action_input.get("event_name", "Unknown event name")}
    2. Start Time: {action_input.get("start_time", "Unknown time")}
    3. End Time: {action_input.get("end_time", "Unknown time")}
    4. Description: {action_input.get("description", "No description provided")}
    5. Invited People: {', '.join(action_input.get("invited_people", [])) if action_input.get("invited_people") else "No one invited"}
    6. Meeting Link: {action_input.get("meet_link", "No meeting link provided")}

    Your task:
    1. Generate a short confirmation response that acknowledges the user’s intent and provides all the meeting details in a natural conversational format.
    2. Ensure that the time is in the "hh:mm of dd/mm/yy" format.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        temperature=0.7,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )

    content = response.choices[0].message.content.strip()
    return content

def format_datetime(datetime_str: str) -> str:
    try:
        # Assuming the input datetime string is in ISO format (e.g., '2025-04-25T15:30:00')
        dt = datetime.fromisoformat(datetime_str)
        return dt.strftime("%H:%M of %d/%m/%Y")
    except ValueError:
        return datetime_str  # Return the original if the format is not correct


if __name__ == "__main__":
    result = identify_user("Hi, I'm Felipe but other people call me when they want to talk to me.")
    print(result["username"])
