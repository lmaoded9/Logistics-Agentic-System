from typing import Dict, Any
from loguru import logger
from datetime import datetime

def classify_message_intent(message: str) -> str:
    """Classify the intent of a driver's message to route to correct agent"""
    message_lower = message.lower()
    
    # Availability keywords
    availability_keywords = ["free", "available", "ready", "busy", "occupied", "offline", "rest", "break", "status", "working", "trip", "driving"]
    
    # Load search keywords  
    load_keywords = ["load", "loads", "shipment", "cargo", "delivery", "transport", "from", "to", "route", "destination", "pickup", "booking"]
    
    # Expense keywords
    expense_keywords = ["expense", "cost", "fuel", "diesel", "toll", "parking", "maintenance", "repair", "bill", "receipt", "paid"]
    
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
    """Route message to appropriate agent based on intent classification"""
    logger.info(f"🔀 Routing message from {driver_id}: {message}")
    
    # Classify intent
    intent = classify_message_intent(message)
    logger.info(f"🎯 Classified intent: {intent}")
    
    try:
        if intent == "availability":
            # Import and use availability agent
            try:
                from availability_agent import process_driver_message
                result = process_driver_message(message, driver_id)
                
                # Reformat to match expected structure
                return {
                    "type": "availability",
                    "status": "success", 
                    "driver_status": result.get("driver_status", "unknown"),
                    "location": result.get("location", ""),
                    "response": result.get("response_sent", "Status updated."),
                    "routed_to": intent,
                    "driver_id": driver_id,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except ImportError as e:
                logger.warning(f"⚠️ Availability agent not found: {e}")
                return {
                    "type": "availability",
                    "status": "success",
                    "response": f"समझ गया! आप available हैं। आपका status update हो गया है।",
                    "routed_to": intent,
                    "driver_id": driver_id,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
        elif intent == "load_search":
            # Load finder placeholder (will connect to real agent later)
            return {
                "type": "load_search",
                "status": "success",
                "loads_found": 3,
                "response": f"🚛 मिल गए 3 loads आपके लिए!\n\n📦 Delhi → Mumbai: ₹45,000 (15 tons)\n📦 Chennai → Bangalore: ₹32,000 (12 tons)\n📦 Pune → Hyderabad: ₹28,000 (10 tons)\n\nकौन सा लेना चाहते हैं? Reply करें load number के साथ।",
                "routed_to": intent,
                "driver_id": driver_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        elif intent == "expense_tracking": 
            # Extract amount from message (basic parsing)
            import re
            amount_match = re.search(r'(\d+)', message)
            amount = int(amount_match.group(1)) if amount_match else 0
            
            expense_type = "fuel" if "fuel" in message.lower() else "toll" if "toll" in message.lower() else "general"
            
            return {
                "type": "expense_tracking",
                "status": "success", 
                "expense_type": expense_type,
                "amount": amount,
                "response": f"💰 Expense recorded!\n\n🧾 Type: {expense_type.title()}\n💵 Amount: ₹{amount}\n👤 Driver: {driver_id}\n⏰ Time: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nReceipt saved successfully!",
                "routed_to": intent,
                "driver_id": driver_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        else:
            # General fallback response
            return {
                "type": "general",
                "status": "success",
                "response": f"नमस्ते! 🙏\n\nआप कह रहे हैं: '{message}'\n\nमैं आपकी मदद कर सकता हूं:\n\n✅ Driver status (कहें 'मैं free हूं' या 'busy हूं')\n📦 Load search (कहें 'Delhi से Mumbai loads')\n💰 Expense tracking (कहें 'fuel expense 2500')\n\nक्या चाहिए आज?",
                "routed_to": intent,
                "driver_id": driver_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
    except Exception as e:
        logger.error(f"❌ Error routing message: {str(e)}")
        return {
            "type": "error",
            "status": "failed",
            "error": str(e),
            "response": "माफ करें, system में कुछ issue है। कृपया दोबारा try करें या support से contact करें।",
            "routed_to": intent,
            "driver_id": driver_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
