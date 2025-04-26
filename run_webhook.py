#!/usr/bin/env python3
"""
Entry point script for running the WhatsApp webhook handler.
This script should be run from the project root directory.
"""

from bot.webhook import webhook

if __name__ == "__main__":
    # This is a simple test to see if the imports work
    print("Webhook module imported successfully!")
    print("To use this in a real Django application, you should:")
    print("1. Configure your Django URLs to point to the webhook view")
    print("2. Run your Django application with 'python manage.py runserver'")
    print("3. Configure your WhatsApp webhook to point to your server URL") 