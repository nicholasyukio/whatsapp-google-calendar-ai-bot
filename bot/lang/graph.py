from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain.graphs import StateGraph
from bot.lang.my_types import BotState, create_initial_state
from bot.lang.nodes import (
    thinking_node,
    check_availability_node,
    create_event_node,
    gen_response_node,
    router
)

def create_calendar_graph() -> StateGraph:
    """Create the calendar management graph."""
    # Create workflow graph
    workflow = StateGraph(BotState)
    
    # Add nodes
    workflow.add_node("thinking", thinking_node)
    workflow.add_node("check_availability", check_availability_node)
    workflow.add_node("create_event", create_event_node)
    workflow.add_node("gen_response", gen_response_node)
    
    # Add edges based on router
    workflow.add_edge("thinking", "router", router)
    workflow.add_edge("check_availability", "router", router)
    workflow.add_edge("create_event", "router", router)
    
    # Set entry point
    workflow.set_entry_point("thinking")
    
    # Compile graph
    return workflow.compile()

def process_message(user_input: str, config: RunnableConfig = None) -> Dict[str, Any]:
    """Process a user message through the graph."""
    # Create initial state
    state = create_initial_state(user_input)
    
    # Get graph
    graph = create_calendar_graph()
    
    # Process message
    result = graph.invoke({"state": state}, config=config)
    
    return {
        "response": result["state"]["final_response"],
        "action_results": result["state"]["action_results"],
        "thinking_results": result["state"]["thinking_results"]
    } 