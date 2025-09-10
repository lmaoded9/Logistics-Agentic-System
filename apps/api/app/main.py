from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger # type: ignore
import sys
import os

# Add the agents folder to Python path
agents_path = os.path.join(os.path.dirname(__file__), "..", "..", "agents", "src")
sys.path.append(agents_path)

# Import the smart agent router instead of individual agents
from agent_router import route_message_to_agent

app = FastAPI(title="Agentic Logistics API - Multi-Agent System")

@app.get("/health")
def health():
    return {"status": "ok", "agents": ["availability", "load_finder", "expense_tracker"]}

class EchoIn(BaseModel):
    text: str

@app.post("/echo")
def echo(inp: EchoIn):
    logger.info(f"echo called with {inp.text}")
    return {"reply": f"echo {inp.text}"}

class ProcessIn(BaseModel):
    message: str
    driver_id: str = "driver_123"

@app.post("/process")
def process_message(inp: ProcessIn):
    """
    Intelligent message processing with multi-agent routing
    Automatically detects intent and routes to appropriate agent
    """
    logger.info(f"Processing message from driver {inp.driver_id}: {inp.message}")
    
    try:
        # Route to appropriate agent based on message content
        result = route_message_to_agent(inp.message, inp.driver_id)
        
        logger.info(f"Agent response: {result}")
        
        return {
            "success": True,
            "message": inp.message,
            "driver_id": inp.driver_id,
            "intent_detected": result.get("routed_to", "unknown"),
            "agent_type": result["type"], 
            "agent_response": result["response"],
            "timestamp": result.get("timestamp", ""),
            "additional_data": {
                key: value for key, value in result.items() 
                if key not in ["type", "response", "routed_to", "driver_id"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Sorry, I couldn't process your message. Please try again."
        }

@app.get("/driver/{driver_id}/status")
def get_driver_status(driver_id: str):
    """Get current status of a driver"""
    logger.info(f"Getting status for driver: {driver_id}")
    
    return {
        "driver_id": driver_id,
        "status": "available",
        "location": "Delhi", 
        "last_updated": "2025-09-10 02:30:00",
        "vehicle_type": "truck"
    }

@app.get("/loads/search")
def search_loads(source: str = "", destination: str = "", vehicle_type: str = "any"):
    """Direct load search endpoint for web dashboard"""
    
    query = f"loads from {source} to {destination}" if source and destination else "available loads"
    
    # Import here to avoid circular imports
    from load_finder_agent import process_load_search
    result = process_load_search(query)
    
    return {
        "success": True,
        "query": query,
        "loads_found": result["loads_found"],
        "response": result["response"]
    }
