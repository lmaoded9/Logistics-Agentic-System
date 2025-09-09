from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger
import sys
import os

# Add the agents folder to Python path so we can import from it
agents_path = os.path.join(os.path.dirname(__file__), "..", "..", "agents", "src")
sys.path.append(agents_path)

# Import our LangGraph agent
from availability_agent import process_availability_message

app = FastAPI(title="Agentic Logistics API")

@app.get("/health")
def health():
    return {"status": "ok"}

class EchoIn(BaseModel):
    text: str

@app.post("/echo")
def echo(inp: EchoIn):
    logger.info(f"echo called with {inp.text}")
    return {"reply": f"echo {inp.text}"}

class ProcessIn(BaseModel):
    message: str
    driver_id: str = "driver_123"  # Optional driver ID with default

@app.post("/process")
def process_message(inp: ProcessIn):
    """
    Process messages using LangGraph workflows
    This endpoint now uses real AI agents with state management
    """
    logger.info(f"Processing message from driver {inp.driver_id}: {inp.message}")
    
    try:
        # Call our LangGraph availability agent
        result = process_availability_message(inp.message, inp.driver_id)
        
        logger.info(f"LangGraph agent response: {result}")
        
        return {
            "success": True,
            "message": inp.message,
            "driver_id": inp.driver_id,
            "agent_response": result["response"],
            "agent_type": result["type"],
            "driver_status": result["driver_status"],
            "location": result["location"],
            "updated_at": result["updated_at"],
            "status": result["status"]
        }
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Sorry, I couldn't process your message. Please try again."
        }

# New endpoint: Get driver status
@app.get("/driver/{driver_id}/status")
def get_driver_status(driver_id: str):
    """
    Get current status of a driver
    Later we'll connect this to a real database
    """
    logger.info(f"Getting status for driver: {driver_id}")
    
    # For now, return mock data
    # Later this will query your database
    return {
        "driver_id": driver_id,
        "status": "available",
        "location": "Delhi", 
        "last_updated": "2025-09-10 01:45:00",
        "vehicle_type": "truck"
    }
