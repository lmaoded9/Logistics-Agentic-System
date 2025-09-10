from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, START, END
from loguru import logger # type: ignore
import json

# Define the state that flows through our workflow
class AvailabilityState(TypedDict):
    messages: List[str]
    driver_id: str
    status: str  # "available", "busy", "offline"
    location: str
    vehicle_type: str
    last_updated: str

# Node functions - each does one specific task
def parse_availability_message(state: AvailabilityState) -> AvailabilityState:
    """Extract availability info from driver message"""
    
    last_message = state["messages"][-1].lower()
    logger.info(f"Parsing availability message: {last_message}")
    
    # Simple parsing logic (later we'll use LLMs for this)
    if any(word in last_message for word in ["free", "available", "ready"]):
        state["status"] = "available"
    elif any(word in last_message for word in ["busy", "occupied", "trip"]):
        state["status"] = "busy"
    elif any(word in last_message for word in ["offline", "rest", "break"]):
        state["status"] = "offline"
    
    # Extract location if mentioned
    if "from" in last_message or "at" in last_message:
        # Simple location extraction (later improve with NLP)
        words = last_message.split()
        for i, word in enumerate(words):
            if word in ["from", "at"] and i + 1 < len(words):
                state["location"] = words[i + 1].capitalize()
                break
    
    logger.info(f"Parsed status: {state['status']}, location: {state.get('location', 'unknown')}")
    return state

def update_driver_database(state: AvailabilityState) -> AvailabilityState:
    """Update driver status in database (mocked for now)"""
    
    logger.info(f"Updating database for driver {state.get('driver_id', 'unknown')}")
    logger.info(f"New status: {state['status']}")
    
    # Here we'd normally update a real database
    # For now, just simulate it
    from datetime import datetime
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return state

def generate_response(state: AvailabilityState) -> AvailabilityState:
    """Generate response message for driver"""
    
    status = state["status"]
    location = state.get("location", "")
    
    if status == "available":
        if location:
            response = f"✅ Great! Marked you as AVAILABLE at {location}. We'll notify you of nearby loads."
        else:
            response = "✅ Great! Marked you as AVAILABLE. We'll notify you when loads come up."
    elif status == "busy":
        response = "📍 Understood. Marked you as BUSY. Focus on your current trip safely!"
    elif status == "offline":
        response = "😴 Got it. Marked you as OFFLINE. Take rest and message when ready for work."
    else:
        response = "❓ I didn't understand your availability status. Try saying 'I'm free' or 'I'm busy'."
    
    # Add response to messages
    state["messages"].append(response)
    return state

# Build the workflow graph
def create_availability_workflow():
    """Create the LangGraph workflow for handling driver availability"""
    
    workflow = StateGraph(AvailabilityState)
    
    # Add nodes
    workflow.add_node("parse", parse_availability_message)
    workflow.add_node("update_db", update_driver_database) 
    workflow.add_node("respond", generate_response)
    
    # Add edges (flow between nodes)
    workflow.add_edge(START, "parse")
    workflow.add_edge("parse", "update_db")
    workflow.add_edge("update_db", "respond")
    workflow.add_edge("respond", END)
    
    # Compile the graph
    app = workflow.compile()
    return app

# Main function to process availability messages
def process_availability_message(message: str, driver_id: str = "driver_123") -> Dict:
    """Process a driver availability message through LangGraph workflow"""
    
    logger.info(f"Processing availability message from driver {driver_id}: {message}")
    
    # Create initial state
    initial_state = {
        "messages": [message],
        "driver_id": driver_id,
        "status": "unknown",
        "location": "",
        "vehicle_type": "",
        "last_updated": ""
    }
    
    # Run the workflow
    workflow = create_availability_workflow()
    final_state = workflow.invoke(initial_state)
    
    return {
        "type": "availability",
        "status": "success",
        "driver_status": final_state["status"],
        "location": final_state.get("location", ""),
        "response": final_state["messages"][-1],
        "updated_at": final_state["last_updated"]
    }

# Test the workflow
if __name__ == "__main__":
    test_messages = [
        "I am free and available at Delhi",
        "Currently busy with a trip",
        "Going offline for rest",
        "Ready for work from Mumbai"
    ]
    
    for msg in test_messages:
        print(f"\n📨 Testing: {msg}")
        result = process_availability_message(msg)
        print(f"🤖 Response: {result['response']}")
        print(f"📊 Status: {result['driver_status']}")
        print("-" * 60)
