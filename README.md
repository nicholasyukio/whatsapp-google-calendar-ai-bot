# WhatsApp Google Calendar AI Bot

A WhatsApp bot that integrates with Google Calendar to schedule, manage, and view events. The bot uses natural language processing to understand user requests and interacts with Google Calendar API to manage events.

## Features

- Natural language processing for calendar commands using LangChain
- Create, cancel, and list calendar events
- Check availability for scheduling
- Conversation memory for context-aware responses
- AWS Lambda deployment using Zappa
- WhatsApp Business API integration

## Prerequisites

- Python 3.10 or higher
- AWS Account with appropriate permissions
- Google Cloud Platform account
- WhatsApp Business API access

## Setup Instructions

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

```
OPENAI_API_KEY=your_openai_api_key
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
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
5. Rename the downloaded file to `credentials.json` and place it in the root directory

### 4. Local Development

```bash
python manage.py runserver
```

The first time you run the application, it will open a browser window asking you to authorize the application to access your Google Calendar. After authorization, a `token.pickle` file will be created to store your credentials.

### 5. AWS Deployment

The project uses Zappa for AWS Lambda deployment. The configuration is in `zappa_settings.json`.

To deploy:

```bash
zappa deploy production
```

To update after changes:

```bash
zappa update production
```

## Project Structure

```
.
├── bot/                    # Main application directory
│   ├── lang/              # Language processing modules
│   ├── whatsapp/          # WhatsApp integration
│   ├── tests/             # Test files
│   ├── views.py           # Django views
│   ├── urls.py            # URL routing
│   └── models.py          # Database models
├── whatsapp_bot/          # Django project settings
├── requirements.txt       # Python dependencies
├── zappa_settings.json    # AWS Lambda deployment settings
└── manage.py             # Django management script
```

## How It Works

The bot follows a workflow that combines natural language processing, calendar management, and WhatsApp communication. Here's how it works:

1. **Message Reception**: When a user sends a message via WhatsApp, it's received through the webhook endpoint in `bot/whatsapp/webhook.py`.

2. **Language Processing**: The message is processed using LangChain in `bot/lang/workflow.py`, which:
   - Understands the user's intent
   - Extracts relevant information (dates, times, people, etc.)
   - Determines the appropriate calendar action

3. **Calendar Operations**: Based on the processed intent, `bot/lang/google_calendar.py` performs the necessary calendar operations:
   - Creating events
   - Checking availability
   - Modifying existing events
   - Retrieving event information

4. **Response Generation**: The bot generates a natural language response and sends it back to the user via WhatsApp using `bot/whatsapp/whatsapp_api.py`.

### Key Components

#### Language Processing (`bot/lang/`)
- `workflow.py`: Core workflow implementation using LangChain
  - Defines the conversation flow
  - Processes user intents
  - Manages conversation context
  - Coordinates between different components

- `prompts.py`: Contains all the prompt templates
  - System prompts for the AI
  - User message templates
  - Response formatting templates

- `database.py`: Manages conversation state
  - Stores conversation history
  - Maintains context between messages
  - Handles user preferences

- `google_calendar.py`: Google Calendar integration
  - Calendar API operations
  - Event management
  - Availability checking
  - Time zone handling

#### WhatsApp Integration (`bot/whatsapp/`)
- `webhook.py`: Handles incoming WhatsApp messages
  - Message validation
  - Request processing
  - Error handling
  - Security verification

- `whatsapp_api.py`: Manages WhatsApp communication
  - Message sending
  - Media handling
  - API authentication
  - Rate limiting

#### Django Components
- `views.py`: HTTP request handling
  - Webhook endpoints
  - API routes
  - Request validation
  - Response formatting

- `urls.py`: URL routing
  - Endpoint definitions
  - URL patterns
  - Route mapping

- `models.py`: Database models
  - User data
  - Conversation history
  - System configuration

## Usage

The bot understands natural language commands for calendar management:

- **Create an event**: "Schedule a meeting with John tomorrow at 2pm"
- **Cancel an event**: "Cancel my meeting with John tomorrow"
- **List events**: "What meetings do I have tomorrow?"
- **Check availability**: "Is 3pm tomorrow available?"

## Development

### Adding New Features

1. Update the language processing modules in `bot/lang/`
2. Add new calendar operations in the appropriate modules
3. Update the views to handle new functionality
4. Add tests for new features

### Testing

```bash
python manage.py test
```

## License

This project is licensed under the terms specified in the LICENSE file.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
