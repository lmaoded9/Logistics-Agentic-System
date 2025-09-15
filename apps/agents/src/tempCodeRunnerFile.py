import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import google.generativeai as genai
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, START, END
from loguru import logger
from datetime import datetime
import json

# Configure Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')

class AvailabilityState(TypedDict):
    messages: List[str]
    driver_id: str
    status: str  # available, busy, offline
    location: str
    vehicle_type: str
    last_updated: str
    confidence: float
    reasoning: str

def analyze_availability_with_gemini(state: AvailabilityState) -> AvailabilityState:
    """Use Gemini to intelligently understand driver availability messages"""
    
    message = state['messages'][-1]
    logger.info(f"Analyzing message with Gemini: {message}")
    
    # Create intelligent prompt for Gemini
    prompt = f"""
    You are an AI assistant for a logistics company in India. Analyze this driver message and extract availability information.

    Driver Message: "{message}"

    Extract the following information:
    1. Driver Status: "available", "busy", or "offline"
    2. Location: City/place mentioned (if any)
    3. Vehicle Type: truck/trailer/tempo (if mentioned)
    4. Confidence: How confident you are (0.0-1.0)
    5. Reasoning: Why you classified it this way

    Consider Indian logistics context:
    - "Free" means available
    - "Khali" means available (Hindi)
    - "Load leke ja raha hun" means busy
    - "Trip pe hun" means busy
    - "Rest kar raha" means offline
    - "Delhi se Mumbai" indicates route/location

    Respond in JSON format:
    {{
        "status": "available/busy/offline",
        "location": "city name or empty string",
        "vehicle_type": "truck/trailer/tempo or empty string",
        "confidence": 0.8,
        "reasoning": "explanation"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        result = json.loads(response.text.strip())
        
        # Update state with Gemini's analysis
        state['status'] = result['status']
        state['location'] = result.get('location', '')
        state['vehicle_type'] = result.get('vehicle_type', '')
        state['confidence'] = result.get('confidence', 0.8)
        state['reasoning'] = result.get('reasoning', '')
        
        logger.info(f"Gemini analysis: {result}")
        
    except Exception as e:
        logger.error(f"Gemini analysis failed: {str(e)}")
        # Fallback to simple logic
        message_lower = message.lower()
        if any(word in message_lower for word in ['free', 'available', 'khali', 'ready']):
            state['status'] = 'available'
        elif any(word in message_lower for word in ['busy', 'trip', 'load']):
            state['status'] = 'busy'
        else:
            state['status'] = 'offline'
        state['confidence'] = 0.5
        state['reasoning'] = 'Fallback analysis due to AI error'
    
    return state

def update_driver_database(state: AvailabilityState) -> AvailabilityState:
    """Update driver status in database (mocked for now)"""
    
    logger.info(f"Updating database for driver {state.get('driver_id', 'unknown')}")
    logger.info(f"New status: {state['status']} at {state.get('location', 'unknown')}")
    
    # Here you'd update real database
    state['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return state

def generate_intelligent_response(state: AvailabilityState) -> AvailabilityState:
    """Generate contextual response using Gemini"""
    
    status = state['status']
    location = state.get('location', '')
    confidence = state.get('confidence', 0.8)
    
    # Create response prompt for Gemini
    response_prompt = f"""
    Generate a helpful response for a truck driver in India's logistics industry.

    Driver Status: {status}
    Location: {location}
    Confidence: {confidence}
    Original Message: {state['messages'][-1]}

    Guidelines:
    - Be friendly and professional
    - Use simple language
    - Acknowledge their status clearly
    - For "available": mention we'll find loads
    - For "busy": wish them safe trip
    - For "offline": acknowledge their break
    - Include location if provided
    - Keep it concise (1-2 sentences)

    Generate response in Hindi and English mix (common in Indian logistics):
    """
    
    try:
        response = model.generate_content(response_prompt)
        intelligent_response = response.text.strip()
        
    except Exception as e:
        logger.error(f"Response generation failed: {str(e)}")
        # Fallback responses
        if status == 'available':
            intelligent_response = f"Great! Marked you as AVAILABLE{' at ' + location if location else ''}. We'll notify you of nearby loads."
        elif status == 'busy':
            intelligent_response = "Understood. Marked you as BUSY. Drive safely!"
        else:
            intelligent_response = "Got it. Marked you as OFFLINE. Take rest!"
    
    state['messages'].append(intelligent_response)
    return state

# Build the LangGraph workflow
def create_availability_workflow():
    """Create intelligent availability workflow with Gemini"""
    
    workflow = StateGraph(AvailabilityState)
    
    # Add nodes
    workflow.add_node("analyze", analyze_availability_with_gemini)
    workflow.add_node("update_db", update_driver_database)
    workflow.add_node("respond", generate_intelligent_response)
    
    # Add edges (flow)
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "update_db")
    workflow.add_edge("update_db", "respond")
    workflow.add_edge("respond", END)
    
    return workflow.compile()

# Main processing function
def process_availability_message(message: str, driver_id: str = "driver123") -> Dict:
    """Process driver availability message with Gemini intelligence"""
    
    logger.info(f"Processing intelligent availability message from driver {driver_id}: {message}")
    
    # Create initial state
    initial_state = {
        'messages': [message],
        'driver_id': driver_id,
        'status': 'unknown',
        'location': '',
        'vehicle_type': '',
        'last_updated': '',
        'confidence': 0.0,
        'reasoning': ''
    }
    
    # Run the intelligent workflow
    workflow = create_availability_workflow()
    final_state = workflow.invoke(initial_state)
    
    return {
        'type': 'availability',
        'status': 'success',
        'driver_status': final_state['status'],
        'location': final_state.get('location', ''),
        'confidence': final_state.get('confidence', 0.8),
        'reasoning': final_state.get('reasoning', ''),
        'response': final_state['messages'][-1],
        'updated_at': final_state['last_updated']
    }

# Test the intelligent agent
if __name__ == "__main__":
    # Test with real Indian logistics messages
    test_messages = [
        "Main free hun Delhi mein, koi load hai kya?",
        "Trip complete kar diya, ab available hun Mumbai se",
        "Load leke ja raha hun Bangalore, 2 din baad free hounga",
        "Rest kar raha hun, kal subah se available rahuga",
        "Khali hun Chennai mein, urgent load chahiye"
    ]
    
    for msg in test_messages:
        print(f"\n{'='*60}")
        print(f"Testing: {msg}")
        result = process_availability_message(msg)
        print(f"Status: {result['driver_status']}")
        print(f"Location: {result['location']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Response: {result['response']}")
        print(f"Reasoning: {result['reasoning']}")
