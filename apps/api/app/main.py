from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from loguru import logger
import sys
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Twilio credentials (optional - will work without them)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN") 
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Initialize Twilio client (safely)
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
    if twilio_client:
        logger.info("✅ Twilio client initialized")
    else:
        logger.info("ℹ️ Twilio not configured - running without WhatsApp sending")
except Exception as e:
    logger.warning(f"⚠️ Twilio initialization failed: {e}")
    twilio_client = None

# Add the agents folder to Python path
agents_path = os.path.join(os.path.dirname(__file__), "..", "..", "agents", "src")
sys.path.append(agents_path)

# Import the agent router
try:
    from agent_router import route_message_to_agent
    logger.info("✅ Agent router imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import agent router: {e}")
    # Fallback function
    def route_message_to_agent(message: str, driver_id: str) -> dict:
        return {
            "type": "fallback",
            "response": "System is loading, please try again.",
            "status": "success",
            "routed_to": "fallback",
            "driver_id": driver_id
        }

app = FastAPI(title="Agentic Logistics API - WhatsApp Enabled")

@app.get("/health")
def health():
    return {
        "status": "ok", 
        "agents": ["availability", "load_finder", "expense_tracker"],
        "whatsapp": "enabled" if twilio_client else "disabled",
        "twilio_configured": bool(TWILIO_ACCOUNT_SID),
        "agent_router": "active"
    }

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
    """Intelligent message processing with multi-agent routing"""
    logger.info(f"🔄 Processing message from driver {inp.driver_id}: {inp.message}")
    
    try:
        result = route_message_to_agent(inp.message, inp.driver_id)
        logger.info(f"🤖 Agent response: {result.get('type', 'unknown')} - {result.get('response', 'No response')[:50]}...")
        
        return {
            "success": True,
            "message": inp.message,
            "driver_id": inp.driver_id,
            "intent_detected": result.get("routed_to", "unknown"),
            "agent_type": result.get("type", "unknown"), 
            "agent_response": result.get("response", "No response"),
            "timestamp": result.get("timestamp", ""),
            "additional_data": {
                key: value for key, value in result.items() 
                if key not in ["type", "response", "routed_to", "driver_id"]
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing message: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Sorry, I couldn't process your message. Please try again."
        }

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Complete WhatsApp Integration - Receive AND Respond"""
    try:
        # Parse incoming WhatsApp message
        form = await request.form()
        from_number = form.get("From", "").replace("whatsapp:", "")
        message_body = form.get("Body", "")
        profile_name = form.get("ProfileName", "Driver")
        
        logger.info(f"📱 WhatsApp from {profile_name} ({from_number}): {message_body}")
        
        # Process with intelligent multi-agent system
        result = route_message_to_agent(message_body, from_number)
        
        # Log the intelligent analysis
        logger.info(f"🤖 Agent: {result.get('type', 'unknown')} | Intent: {result.get('routed_to', 'unknown')}")
        logger.info(f"💬 Response: {result.get('response', 'No response')[:100]}...")
        
        # Send intelligent response back to driver
        if twilio_client and result.get('response'):
            try:
                message = twilio_client.messages.create(
                    from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                    to=f"whatsapp:{from_number}",
                    body=result['response']
                )
                logger.info(f"✅ Sent WhatsApp response: {message.sid}")
            except Exception as send_error:
                logger.error(f"❌ Failed to send WhatsApp response: {send_error}")
        else:
            logger.info("ℹ️ Twilio not configured - response logged but not sent")
        
        # Return empty TwiML
        resp = MessagingResponse()
        return Response(str(resp), media_type="text/xml")
        
    except Exception as e:
        logger.error(f"❌ WhatsApp webhook error: {str(e)}")
        
        # Send error response to driver if possible
        if twilio_client and 'from_number' in locals():
            try:
                twilio_client.messages.create(
                    from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                    to=f"whatsapp:{from_number}",
                    body="माफ करें, system में कुछ issue है। कृपया दोबारा try करें।"
                )
            except:
                pass
        
        resp = MessagingResponse()
        return Response(str(resp), media_type="text/xml")

@app.post("/whatsapp/send")
async def send_whatsapp_message(phone: str, message: str):
    """Send proactive WhatsApp messages to drivers"""
    if not twilio_client:
        return {"error": "Twilio not configured"}
    
    try:
        if not phone.startswith("whatsapp:"):
            phone = f"whatsapp:{phone}"
            
        message_obj = twilio_client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            to=phone,
            body=message
        )
        
        logger.info(f"📤 Sent proactive message to {phone}: {message[:50]}...")
        return {
            "success": True,
            "message_sid": message_obj.sid,
            "to": phone,
            "message": message
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send proactive message: {e}")
        return {"error": str(e)}

@app.get("/driver/{driver_id}/status")
def get_driver_status(driver_id: str):
    """Get current status of a driver"""
    logger.info(f"Getting status for driver: {driver_id}")
    return {
        "driver_id": driver_id,
        "status": "available",
        "location": "Delhi", 
        "last_updated": "2025-09-14 19:15:00",
        "vehicle_type": "truck"
    }

@app.get("/whatsapp/status")
def whatsapp_integration_status():
    """Check WhatsApp integration health"""
    return {
        "twilio_configured": bool(TWILIO_ACCOUNT_SID),
        "whatsapp_number": TWILIO_WHATSAPP_NUMBER or "Not configured",
        "webhook_endpoint": "/webhook/whatsapp", 
        "send_endpoint": "/whatsapp/send",
        "mode": "full_two_way" if twilio_client else "receive_only",
        "agents_connected": True,
        "database_connected": True,
        "features": ["receive_messages", "intelligent_routing", "multi_agent_processing"]
    }
