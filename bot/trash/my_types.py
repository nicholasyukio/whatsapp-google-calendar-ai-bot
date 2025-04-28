from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import json
import logging
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logger = logging.getLogger(__name__)

# Initialize the model
model = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0
)

# Initialize embeddings model
embeddings_model = OpenAIEmbeddings()

# Define valid actions with descriptions
VALID_ACTIONS = {
    "check_availability": "Check if a time slot is available in the calendar",
    "create_event": "Create a new calendar event",
    "cancel_event": "Cancel an existing calendar event",
    "list_events": "List events for a specific date",
    "gen_response": "Generate a response to the user"
}

def get_embedding(text: str) -> List[float]:
    """Get embedding for a text."""
    return embeddings_model.embed_query(text)

def find_most_similar_action(invalid_action: str) -> str:
    """
    Find the most semantically similar valid action to the invalid action.
    
    Args:
        invalid_action (str): The invalid action returned by the LLM
        
    Returns:
        str: The most similar valid action
    """
    try:
        # Create embeddings for each valid action
        valid_embeddings = {}
        for action, description in VALID_ACTIONS.items():
            # Create a combined text of action and description
            text = f"{action}: {description}"
            # Get embedding
            embedding = get_embedding(text)
            valid_embeddings[action] = embedding
        
        # Create embedding for the invalid action
        invalid_embedding = get_embedding(invalid_action)
        
        # Find the most similar action
        max_similarity = -1
        most_similar_action = "gen_response"  # Default fallback
        
        for action, embedding in valid_embeddings.items():
            similarity = cosine_similarity([invalid_embedding], [embedding])[0][0]
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_action = action
        
        logger.info(f"Invalid action '{invalid_action}' mapped to '{most_similar_action}' with similarity {max_similarity:.4f}")
        return most_similar_action
    except Exception as e:
        logger.error(f"Error finding similar action: {str(e)}")
        return "gen_response"  # Default fallback

class CalendarEvent(TypedDict):
    title: str
    datetime: str
    duration: Optional[int]  # in minutes
    description: Optional[str]

class ActionResult(TypedDict):
    action: str
    status: str  # "success", "failure", "pending"
    data: Dict[str, Any]
    timestamp: str

class ThinkingResult(TypedDict):
    required_info: List[str]  # What information is still needed
    suggested_action: str  # What action should be taken next
    reasoning: str  # Why this action was chosen

class ActionResponse(TypedDict):
    status: str  # "done", "not_enough_info", "impossible"
    info: str  # Action-specific information
    next_action: Optional[str]  # Next action to execute

class BotState(TypedDict):
    user_input: str
    action_results: List[ActionResult]
    thinking_results: List[ThinkingResult]
    iteration_count: int
    final_response: Optional[str]
    conversation_history: List[Dict[str, Any]]

def create_initial_state(user_input: str) -> BotState:
    """Create initial bot state."""
    return {
        "user_input": user_input,
        "action_results": [],
        "thinking_results": [],
        "iteration_count": 0,
        "final_response": None,
        "conversation_history": []
    }

def safe_parse_json(content: str, required_keys: List[str]) -> Dict[str, Any]:
    """Parse JSON content safely with required key validation."""
    try:
        # First try direct JSON parsing
        result = json.loads(content)
        
        # Validate required keys
        if not all(key in result for key in required_keys):
            raise ValueError(f"Missing required keys: {[k for k in required_keys if k not in result]}")
            
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse JSON directly: {str(e)}")
        
        # If direct parsing fails, use LLM to fix the JSON
        prompt = f"""Fix the following text to be valid JSON. 
        The JSON must have these exact keys: {', '.join(required_keys)}.
        Return ONLY the fixed JSON, nothing else.
        
        Text to fix:
        {content}"""
        
        try:
            # Get fixed JSON from LLM
            response = model.invoke([{"role": "user", "content": prompt}])
            fixed_json = response.content.strip()
            
            # Try parsing the fixed JSON
            result = json.loads(fixed_json)
            
            # Validate required keys
            if not all(key in result for key in required_keys):
                # If still missing keys, create a default response
                result = {key: None for key in required_keys}
                result["status"] = "impossible"
                result["info"] = "Failed to extract required information"
            
            return result
        except Exception as e:
            logger.error(f"Failed to parse JSON even with LLM help: {str(e)}")
            # Return a safe default response
            return {key: None for key in required_keys}

MAX_ITERATIONS = 5  # Maximum number of node iterations before forcing response generation

# Base action template
def create_action_prompt(action_name: str, description: str) -> str:
    return f"""
    You are a helpful assistant executing the action: {action_name}
    
    Description: {description}
    
    Return a response in this format:
    {{
        "status": "done/not_enough_info/impossible",
        "info": "detailed information about the action result",
        "next_action": "next_action_name"
    }}
    """

def think_node(next_action: str) -> Dict[str, Any]:
    return {
        "current_action": "think",
        "results": {
            "think": {
                "status": "done",
                "info": f"Next action: {next_action}",
                "next_action": next_action
            }
        },
        "next_action": next_action,
        "action_results": []
    } 