# dynamodb.py
import os
import boto3
import datetime
from typing import Optional, Tuple

is_local = os.path.exists('.env')

# Load environment variables from .env
if is_local:
    from dotenv import load_dotenv
    load_dotenv()

# Initialize boto3 session with credentials from .env
session = boto3.Session(
    aws_access_key_id=os.getenv("BOTO_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BOTO_SECRET_ACCESS_KEY"),
    region_name=os.getenv("BOTO_REGION")
)

# Set your table name
TABLE_NAME = "whatsapp-google-calendar-ai-bot-context"

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def create_table():
    """
    Create a DynamoDB table to store bot contexts.
    Run this once.
    """
    try:
        dynamodb_client = boto3.client('dynamodb')

        response = dynamodb_client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
            ],
            BillingMode='PAY_PER_REQUEST',  # So you don't have to set capacity units manually
        )
        print("Creating table...")
        dynamodb_client.get_waiter('table_exists').wait(TableName=TABLE_NAME)
        print("Table created successfully.")
    
    except dynamodb_client.exceptions.ResourceInUseException:
        print("Table already exists.")

def save_state(user_id: str, state: dict):
    """
    Save or update the user's state in the database.
    """

    table.put_item(
        Item=state
    )

def load_state(user_id: str) -> dict:
    """
    Load a user's context and createdAt timestamp from the database.
    
    Returns:
        state if found, else None
    """
    response = table.get_item(
        Key={'user_id': user_id}
    )
    state = response.get('Item')
    if state:
        return state
    return None

def is_context_expired(updated_at_str: str, threshold_minutes: int = 1440) -> bool:
    """
    Check if a context is older than a threshold (default 1440 minutes: 24 hours).
    """
    updated_at = datetime.datetime.fromisoformat(updated_at_str)
    now = datetime.datetime.utcnow()
    return (now - updated_at) > datetime.timedelta(minutes=threshold_minutes)

if __name__ == "__main__":
    create_table()
