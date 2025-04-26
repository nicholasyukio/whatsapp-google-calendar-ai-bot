# WhatsApp Google Calendar AI Bot

A WhatsApp bot that integrates with Google Calendar to schedule, manage, and view events.

## Features

- Natural language processing for calendar commands
- Create, cancel, and list calendar events
- Check availability for scheduling
- Conversation memory for context-aware responses

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

```
OPENAI_API_KEY=your_openai_api_key
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

### 3. Set Up Google Calendar API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" as the application type
   - Download the client configuration file
5. Rename the downloaded file to `credentials.json` and place it in the root directory of the project

### 4. Run the Application

```bash
python manage.py runserver
```

The first time you run the application, it will open a browser window asking you to authorize the application to access your Google Calendar. After authorization, a `token.pickle` file will be created to store your credentials.

### 5. Set Up Twilio Webhook

1. Go to the [Twilio Console](https://www.twilio.com/console)
2. Set up a WhatsApp Sandbox or connect your WhatsApp Business API
3. Configure the webhook URL to point to your application's `/webhook` endpoint
4. Make sure to use HTTPS for the webhook URL (you can use ngrok for local development)

## Usage

Send messages to your WhatsApp number to interact with the bot:

- **Create an event**: "Schedule a meeting with John tomorrow at 2pm"
- **Cancel an event**: "Cancel my meeting with John tomorrow"
- **List events**: "What meetings do I have tomorrow?"
- **Check availability**: "Is 3pm tomorrow available?"

## Development

### Project Structure

- `bot/` - Main application directory
  - `langchain_utils.py` - LangChain integration for natural language processing
  - `google_calendar.py` - Google Calendar API integration
  - `views.py` - Django views for handling webhooks
  - `urls.py` - URL routing
  - `models.py` - Database models

### Adding New Features

1. Update the response schemas in `langchain_utils.py` to include new fields
2. Add new functions to `google_calendar.py` for additional calendar operations
3. Update the `_process_calendar_action` method in `CalendarAssistant` class to handle new actions
