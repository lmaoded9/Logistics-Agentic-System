import os
import json
import time
from datetime import datetime
from typing import TypedDict

import google.generativeai as genai
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from loguru import logger
from pydantic import BaseModel
from supabase import create_client, Client

# --- 1. Load Environment Variables ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")

# Database configuration
DATABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
if DATABASE_ENABLED:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("✅ Supabase database connection established")
else:
    logger.warning("⚠️ Database not configured - using mock storage")
    supabase = None

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)
# Using the model name you have access to. If this still fails, revert to 'gemini-1.5-flash'.
MODEL = genai.GenerativeModel('gemini-2.5-flash')

# Business logic constants
SUPPORTED_CITIES = [
    "Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata", "Pune", "Hyderabad",
    "Ahmedabad", "Surat", "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore"
]
SUPPORTED_VEHICLES = ["truck", "trailer", "tempo", "container", "tanker"]

# --- 2. Pydantic Schema ---
class DriverStatusAnalysis(BaseModel):
    """Schema for parsing driver status from a message."""
    status: str
    location: str
    vehicle_type: str
    confidence: float
    reasoning: str

    class Config:
        extra = "ignore"

class AvailabilityState(TypedDict):
    """The state that flows through the LangGraph workflow."""
    original_message: str
    response_message: str
    driver_id: str
    status: str
    location: str
    vehicle_type: str
    last_updated: str
    confidence: float
    reasoning: str
    error: str | None

# --- 3. Database Functions ---
def ensure_driver_exists(driver_id: str) -> bool:
    if not DATABASE_ENABLED: return True
    try:
        if not supabase.table('drivers').select('driver_id').eq('driver_id', driver_id).execute().data:
            supabase.table('drivers').insert({'driver_id': driver_id, 'current_status': 'offline'}).execute()
            logger.info(f"✅ Created new driver record: {driver_id}")
        return True
    except Exception as e:
        logger.error(f"❌ DB Error in ensure_driver_exists: {e}")
        return False

def save_driver_status(driver_id: str, status: str, location: str, vehicle_type: str) -> bool:
    if not DATABASE_ENABLED: return True
    try:
        supabase.table('drivers').update({
            'current_status': status, 'current_location': location,
            'vehicle_type': vehicle_type, 'last_updated': datetime.now().isoformat()
        }).eq('driver_id', driver_id).execute()
        return True
    except Exception as e: return False

def save_interaction(state: AvailabilityState) -> bool:
    if not DATABASE_ENABLED: return True
    try:
        if not ensure_driver_exists(state['driver_id']): return False
        supabase.table('driver_interactions').insert({
            'driver_id': state['driver_id'], 'original_message': state['original_message'],
            'detected_status': state['status'], 'detected_location': state['location'],
            'detected_vehicle_type': state['vehicle_type'], 'confidence': float(state['confidence']),
            'reasoning': state['reasoning'], 'response_message': state['response_message'],
            'error_details': state.get('error')
        }).execute()
        return True
    except Exception as e: return False

# --- 4. Enhanced Workflow Nodes ---
def analyze_availability(state: AvailabilityState) -> AvailabilityState:
    message = state['original_message']
    driver_id = state['driver_id']
    logger.info(f"🔍 Analyzing message from {driver_id}: '{message}'")

    if not ensure_driver_exists(driver_id):
        state.update({"status": "error", "reasoning": "Driver creation failed", "error": f"Failed to create record for {driver_id}"})
        return state

    prompt = f"""
    Analyze this Indian truck driver message: "{message}"

    Rules:
    - Status MUST be "available", "busy", or "offline".
    - Location: Extract city from {SUPPORTED_CITIES}. If no city is found, use an empty string "".
    - Vehicle: Extract from {SUPPORTED_VEHICLES}. If no vehicle is found, use an empty string "".
    - Confidence: A float from 0.0 to 1.0.
    - Reasoning: A brief, one-sentence explanation.

    IMPORTANT: You must return ALL fields. For location and vehicle_type, return "" if they are not mentioned.
    """
    try:
        response = MODEL.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=DriverStatusAnalysis
            )
        )
        analysis_dict = json.loads(response.text)
        analysis = DriverStatusAnalysis(**analysis_dict)

        logger.info(f"✅ Gemini analysis: {analysis.status} ({analysis.confidence:.2f})")
        state.update({
            "status": analysis.status, "location": analysis.location,
            "vehicle_type": analysis.vehicle_type, "confidence": analysis.confidence,
            "reasoning": analysis.reasoning, "error": None
        })
    except Exception as e:
        logger.error(f"❌ Gemini analysis failed: {e}. Using fallback.")
        message_lower = message.lower()
        status = 'unknown'
        if any(word in message_lower for word in ['busy', 'trip pe', 'load leke', 'ja raha']):
            status = 'busy'
        elif any(word in message_lower for word in ['rest', 'break', 'offline', 'kal subah']):
            status = 'offline'
        elif any(word in message_lower for word in ['free', 'available', 'khali', 'complete']):
            status = 'available'
        else:
            status = 'busy' if any(word in message_lower for word in ['load', 'trip', 'delivery']) else 'available'

        location = next((city for city in SUPPORTED_CITIES if city.lower() in message_lower), "")
        vehicle_type = next((vehicle for vehicle in SUPPORTED_VEHICLES if vehicle in message_lower), "")
        state.update({
            "status": status, "location": location, "vehicle_type": vehicle_type,
            "confidence": 0.8, "reasoning": f"Fallback logic detected '{status}'", "error": None
        })
    return state

def update_driver_database(state: AvailabilityState) -> AvailabilityState:
    if state.get("error"): return state
    success = save_driver_status(state['driver_id'], state['status'], state['location'], state['vehicle_type'])
    if success: state['last_updated'] = datetime.now().isoformat()
    else: state['error'] = "Database update failed"
    return state

def generate_response(state: AvailabilityState) -> AvailabilityState:
    """Generates a contextual response for the driver."""
    if state.get("error"):
        state['response_message'] = "Apka message mil gaya hai. System mein kuch issue hai, jald theek kar denge."
        return state

    # ✅ FIX: Updated prompt to ask for a single, clean response.
    prompt = f"""
    You are a logistics coordinator. An Indian truck driver sent this message: "{state['original_message']}"
    Your system analyzed their status as '{state['status']}' in '{state.get('location', 'an unknown location')}'.

    Your task is to write a single, friendly, and professional response in a mix of Hindi and English.
    
    IMPORTANT INSTRUCTIONS:
    - DO NOT provide multiple options.
    - DO NOT use markdown like bullet points, asterisks for bolding, or quotes.
    - The response should be a single, clean line of text.
    
    Generate the response now.
    """
    try:
        response = MODEL.generate_content(prompt)
        
        # Clean up any residual markdown just in case
        clean_response = response.text.strip().replace("*", "").replace("\"", "")
        state['response_message'] = clean_response
        
        logger.info("✅ Response generated successfully")
    except Exception as e:
        logger.error(f"❌ Response generation failed: {e}. Using template response.")
        status = state['status']
        location = state.get('location', '')
        if status == 'available':
            state['response_message'] = f"Perfect! Aap {location + ' mein ' if location else ''}available hain. Load dhundte hain."
        elif status == 'busy':
            state['response_message'] = "Samjha Bhai. Safe driving! Trip complete hone par update karna."
        elif status == 'offline':
            state['response_message'] = "Theek hai. Rest karo, available hone par message karna."
        else:
            state['response_message'] = "Message samjh gaya. Kuch aur help chahiye?"
    return state

def log_interaction(state: AvailabilityState) -> AvailabilityState:
    if not save_interaction(state):
        logger.warning(f"⚠️ Failed to log interaction for {state['driver_id']}")
    return state

# --- 5. Workflow Creation ---
def create_workflow() -> StateGraph:
    workflow = StateGraph(AvailabilityState)
    workflow.add_node("analyze", analyze_availability)
    workflow.add_node("update_db", update_driver_database)
    workflow.add_node("respond", generate_response)
    workflow.add_node("log_interaction", log_interaction)
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "update_db")
    workflow.add_edge("update_db", "respond")
    workflow.add_edge("respond", "log_interaction")
    workflow.add_edge("log_interaction", END)
    return workflow.compile()

APP = create_workflow()

# --- 6. Main Processing Function ---
def process_driver_message(message: str, driver_id: str) -> dict:
    logger.info(f"🚀 [START] Processing for driver '{driver_id}'")
    initial_state = AvailabilityState(
        original_message=message, driver_id=driver_id, response_message="", status="unknown",
        location="", vehicle_type="", last_updated="", confidence=0.0, reasoning="", error=None
    )
    final_state = APP.invoke(initial_state)
    logger.info(f"✅ [END] Processing complete for driver '{driver_id}'")
    return {
        'driver_id': final_state['driver_id'], 'analysis_status': 'success' if not final_state.get('error') else 'failure',
        'driver_status': final_state['status'], 'location': final_state['location'],
        'vehicle_type': final_state['vehicle_type'], 'confidence': final_state['confidence'],
        'reasoning': final_state['reasoning'], 'response_sent': final_state['response_message'],
        'error_details': final_state.get('error'), 'database_enabled': DATABASE_ENABLED
    }

# --- 7. Database Query Functions ---
def get_driver_status(driver_id: str) -> dict:
    if not DATABASE_ENABLED:
        return {'status': 'Database not enabled'}
    try:
        result = supabase.table('drivers').select('*').eq('driver_id', driver_id).execute()
        return result.data[0] if result.data else {'status': 'Driver not found'}
    except Exception as e:
        logger.error(f"❌ Failed to get driver status: {e}")
        return {'error': str(e)}

# --- Test Cases ---
if __name__ == "__main__":
    test_cases = [
        ("Main free hun Delhi mein, koi load hai kya?", "driver-001"),
        ("Trip complete kar diya, ab available hun Mumbai se", "driver-002"),
        ("Load leke ja raha hun Bangalore, 2 din baad free hounga", "driver-003"),
        ("Rest kar raha hun, kal subah se available rahuga", "driver-004"),
        ("Khali hun Chennai mein, urgent load chahiye", "driver-005"),
        ("Busy hun delivery kar raha hun", "driver-006"),
        ("Break le raha hun, thoda rest", "driver-007")
    ]
    print(f"🗄️ Database Status: {'✅ Connected' if DATABASE_ENABLED else '❌ Mock Mode'}")
    for msg, driver in test_cases:
        print(f"\n{'='*80}")
        print(f"INPUT ==> Driver: {driver}, Message: '{msg}'")
        result = process_driver_message(msg, driver)
        print(f"OUTPUT ==> \n{json.dumps(result, indent=2)}")
        if DATABASE_ENABLED:
            status = get_driver_status(driver)
            print(f"DATABASE STATUS ==> {status}")
        print(f"{'='*80}")
        time.sleep(2)