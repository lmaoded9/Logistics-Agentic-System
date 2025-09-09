from typing import Dict
from loguru import logger

# Simple agent that processes logistics-related queries
def process_logistics_query(query: str) -> Dict[str, str]:
    """
    A simple agent that handles basic logistics queries
    Later we'll replace this with proper LangGraph workflows
    """
    logger.info(f"Agent processing query: {query}")
    
    # Simple keyword matching for now
    query_lower = query.lower()
    
    if "available" in query_lower or "free" in query_lower:
        return {
            "type": "availability",
            "response": f"Marked driver as available. Query: {query}",
            "status": "success"
        }
    elif "load" in query_lower or "shipment" in query_lower:
        return {
            "type": "load_search", 
            "response": f"Searching for loads matching: {query}",
            "status": "success"
        }
    elif "expense" in query_lower or "cost" in query_lower:
        return {
            "type": "expense",
            "response": f"Recording expense: {query}",
            "status": "success"
        }
    else:
        return {
            "type": "general",
            "response": f"I understand you said: {query}. I'm learning to help with logistics!",
            "status": "success"
        }

if __name__ == "__main__":
    # Test the agent
    test_queries = [
        "I am available for trips",
        "Looking for loads from Delhi to Mumbai", 
        "Fuel expense 5000 rupees",
        "Hello how are you"
    ]
    
    for query in test_queries:
        result = process_logistics_query(query)
        print(f"Query: {query}")
        print(f"Response: {result}")
        print("-" * 50)
