from datetime import datetime #import added
from typing import Dict, Any
from loguru import logger # type: ignore
from availability_agent import process_availability_message
from load_finder_agent import process_load_search
from expense_tracker_agent import process_expense_message


def classify_message_intent(message: str) -> str:
    """
    Classify the intent of a driver's message to route to correct agent
    In production, this would use a trained ML model or LLM
    """
    
    message_lower = message.lower()
    
    # Availability keywords
    availability_keywords = [
        "free", "available", "ready", "busy", "occupied", "offline", 
        "rest", "break", "status", "working", "trip", "driving"
    ]
    
    # Load search keywords  
    load_keywords = [
        "load", "loads", "shipment", "cargo", "delivery", "transport",
        "from", "to", "route", "destination", "pickup", "booking"
    ]
    
    # Expense keywords
    expense_keywords = [
        "expense", "cost", "fuel", "diesel", "toll", "parking", 
        "maintenance", "repair", "bill", "receipt", "paid"
    ]
    
    # Count keyword matches
    availability_score = sum(1 for word in availability_keywords if word in message_lower)
    load_score = sum(1 for word in load_keywords if word in message_lower)
    expense_score = sum(1 for word in expense_keywords if word in message_lower)
    
    # Determine intent based on highest score
    if load_score > availability_score and load_score > expense_score:
        return "load_search"
    elif expense_score > availability_score and expense_score > load_score:
        return "expense_tracking"
    elif availability_score > 0:
        return "availability"
    else:
        # Default fallback - analyze context
        if any(word in message_lower for word in ["find", "search", "looking", "need"]):
            return "load_search"
        else:
            return "general"


def route_message_to_agent(message: str, driver_id: str) -> Dict[str, Any]:
    """
    Route message to appropriate agent based on intent classification
    """
    
    logger.info(f"Routing message from {driver_id}: {message}")
    
    # Classify intent
    intent = classify_message_intent(message)
    logger.info(f"Classified intent: {intent}")
    
    try:
        if intent == "availability":
            result = process_availability_message(message, driver_id)
            
        elif intent == "load_search":
            result = process_load_search(message, driver_id)
            
        elif intent == "expense_tracking":
            # Now using real expense tracker agent
            result = process_expense_message(message, driver_id)
            
        else:
            # General fallback response
            result = {
                "type": "general",
                "status": "success",
                "response": f"👋 I understand you said: '{message}'. \n\nI can help you with:\n• **Driver availability** (say 'I'm free' or 'I'm busy')\n• **Load search** (say 'loads from Delhi to Mumbai')\n• **Expense tracking** (say 'fuel expense ₹2500 at Delhi')\n\nHow can I assist you today?",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Add routing metadata
        result["routed_to"] = intent
        result["driver_id"] = driver_id
        
        logger.info(f"Successfully routed to {intent} agent")
        return result
        
    except Exception as e:
        logger.error(f"Error routing message: {str(e)}")
        return {
            "type": "error",
            "status": "failed",
            "error": str(e),
            "response": "❌ Sorry, I encountered an error processing your message. Please try again or contact support.",
            "routed_to": intent,
            "driver_id": driver_id
        }



# Test the router
if __name__ == "__main__":
    test_messages = [
        "I am free and available at Delhi",
        "Looking for loads from Mumbai to Bangalore", 
        "Fuel expense 3000 rupees",
        "Hello, how are you?",
        "Need urgent loads for 20 ton truck",
        "Currently busy with delivery"
    ]
    
    for msg in test_messages:
        print(f"\n📨 Message: {msg}")
        intent = classify_message_intent(msg)
        print(f"🎯 Intent: {intent}")
        
        result = route_message_to_agent(msg, "test_driver")
        print(f"🤖 Agent: {result['type']}")
        print(f"📝 Response: {result['response'][:100]}...")
        print("-" * 60)
