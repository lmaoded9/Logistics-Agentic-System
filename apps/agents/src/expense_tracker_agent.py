from typing import Dict, List, TypedDict, Optional
from langgraph.graph import StateGraph, START, END
from loguru import logger # type: ignore
import json
import re
from datetime import datetime
import random

# State for expense tracking workflow
class ExpenseState(TypedDict):
    message: str
    driver_id: str
    expense_type: str  # fuel, toll, parking, maintenance, food, other
    amount: float
    location: str
    receipt_number: str
    vendor_name: str
    timestamp: str
    trip_id: Optional[str]
    extracted_data: Dict
    response_message: str
    validation_status: str

# Mock expense categories and validation rules
EXPENSE_CATEGORIES = {
    "fuel": {"keywords": ["fuel", "diesel", "petrol", "gas", "pump"], "max_amount": 50000},
    "toll": {"keywords": ["toll", "highway", "expressway", "plaza"], "max_amount": 5000},
    "parking": {"keywords": ["parking", "stand", "halt"], "max_amount": 1000},
    "maintenance": {"keywords": ["repair", "service", "maintenance", "spare", "tyre"], "max_amount": 25000},
    "food": {"keywords": ["food", "meal", "dhaba", "restaurant", "tea", "snacks"], "max_amount": 2000},
    "other": {"keywords": [], "max_amount": 10000}
}

def parse_expense_message(state: ExpenseState) -> ExpenseState:
    """Extract expense information from driver message or receipt data"""
    
    message = state["message"].lower()
    logger.info(f"Parsing expense message: {message}")
    
    # Extract amount using regex
    amount_patterns = [
    r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # ₹1,500 or ₹1500.50
    r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*rupees?',  # 1500 rupees
    r'rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # Rs. 1500
    r'amount\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # amount: 1500
    r'paid\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # paid 1500
    r'cost\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',   # cost 1500
    r'expense\s+(\d+(?:,\d{3})*(?:\.\d{2})?)',  # expense 15000
    r'fee\s+(\d+(?:,\d{3})*(?:\.\d{2})?)',     # fee 200
    r'(?:fuel|diesel|petrol)\s+(\d+(?:,\d{3})*(?:\.\d{2})?)',  # diesel 3500
    r'(?:^|\s)(\d{3,6})(?:\s|$)',  # standalone numbers 3-6 digits
]
    
    extracted_amount = 0.0
    for pattern in amount_patterns:
        match = re.search(pattern, message)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                extracted_amount = float(amount_str)
                break
            except ValueError:
                continue
    
    state["amount"] = extracted_amount
    
    # Categorize expense type
    detected_category = "other"
    max_keywords = 0
    
    for category, config in EXPENSE_CATEGORIES.items():
        keyword_matches = sum(1 for keyword in config["keywords"] if keyword in message)
        if keyword_matches > max_keywords:
            max_keywords = keyword_matches
            detected_category = category
    
    state["expense_type"] = detected_category
    
    # Extract location
    location_patterns = [
        r'at\s+([a-zA-Z\s]+?)(?:\s|$|,)',
        r'in\s+([a-zA-Z\s]+?)(?:\s|$|,)', 
        r'from\s+([a-zA-Z\s]+?)(?:\s|$|,)',
        r'near\s+([a-zA-Z\s]+?)(?:\s|$|,)'
    ]
    
    extracted_location = ""
    for pattern in location_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            extracted_location = match.group(1).strip().title()
            break
    
    state["location"] = extracted_location
    
    # Extract receipt/transaction details
    receipt_patterns = [
        r'receipt\s*(?:no|number|#)?\s*:?\s*([A-Z0-9]+)',
        r'bill\s*(?:no|number|#)?\s*:?\s*([A-Z0-9]+)',
        r'transaction\s*(?:id|#)?\s*:?\s*([A-Z0-9]+)'
    ]
    
    receipt_number = ""
    for pattern in receipt_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            receipt_number = match.group(1)
            break
    
    # Generate receipt number if not found
    if not receipt_number and extracted_amount > 0:
        receipt_number = f"EXP{random.randint(10000, 99999)}"
    
    state["receipt_number"] = receipt_number
    
    # Extract vendor name
    vendor_patterns = [
        r'from\s+([A-Za-z\s&]+?)(?:\s+(?:pump|station|plaza|dhaba)|$)',
        r'at\s+([A-Za-z\s&]+?)(?:\s+(?:pump|station|plaza|dhaba)|$)',
        r'vendor\s*:?\s*([A-Za-z\s&]+?)(?:\s|$|,)'
    ]
    
    vendor_name = ""
    for pattern in vendor_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            vendor_name = match.group(1).strip().title()
            if len(vendor_name) > 3:  # Avoid single words like "the", "and"
                break
    
    state["vendor_name"] = vendor_name
    state["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"Extracted - Type: {state['expense_type']}, Amount: ₹{state['amount']}, Location: {state['location']}")
    return state

def validate_expense_data(state: ExpenseState) -> ExpenseState:
    """Validate extracted expense data for accuracy and completeness"""
    
    logger.info("Validating expense data...")
    
    validation_errors = []
    warnings = []
    
    # Amount validation
    if state["amount"] <= 0:
        validation_errors.append("Amount not found or invalid")
    elif state["amount"] > EXPENSE_CATEGORIES[state["expense_type"]]["max_amount"]:
        warnings.append(f"Amount seems high for {state['expense_type']} (₹{state['amount']:,.2f})")
    
    # Category-specific validation
    if state["expense_type"] == "fuel" and state["amount"] < 100:
        warnings.append("Fuel amount seems unusually low")
    
    if state["expense_type"] == "toll" and state["amount"] > 2000:
        warnings.append("Toll amount seems high - please verify")
    
    # Location validation
    if not state["location"] and state["expense_type"] in ["fuel", "toll", "parking"]:
        warnings.append("Location not specified - this may be required for reimbursement")
    
    # Set validation status
    if validation_errors:
        state["validation_status"] = "failed"
    elif warnings:
        state["validation_status"] = "warning"  
    else:
        state["validation_status"] = "passed"
    
    # Store validation results
    state["extracted_data"] = {
        "validation_errors": validation_errors,
        "warnings": warnings,
        "confidence_score": calculate_confidence_score(state)
    }
    
    logger.info(f"Validation status: {state['validation_status']}")
    return state

def calculate_confidence_score(state: ExpenseState) -> float:
    """Calculate confidence score based on extracted data completeness"""
    
    score = 0.0
    
    # Amount extraction (40% weight)
    if state["amount"] > 0:
        score += 0.4
    
    # Category detection (20% weight)  
    if state["expense_type"] != "other":
        score += 0.2
    
    # Receipt number (15% weight)
    if state["receipt_number"]:
        score += 0.15
    
    # Location (15% weight)
    if state["location"]:
        score += 0.15
    
    # Vendor name (10% weight)
    if state["vendor_name"]:
        score += 0.1
    
    return round(score * 100, 1)

def save_expense_record(state: ExpenseState) -> ExpenseState:
    """Save expense record to database (mocked for now)"""
    
    logger.info(f"Saving expense record for driver {state['driver_id']}")
    
    # In production, this would save to database
    expense_record = {
        "expense_id": f"EXP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "driver_id": state["driver_id"],
        "type": state["expense_type"], 
        "amount": state["amount"],
        "location": state["location"],
        "vendor": state["vendor_name"],
        "receipt_number": state["receipt_number"],
        "timestamp": state["timestamp"],
        "trip_id": state.get("trip_id"),
        "validation_status": state["validation_status"],
        "confidence_score": state["extracted_data"]["confidence_score"]
    }
    
    # Mock database save
    logger.info(f"Expense record saved: {expense_record['expense_id']}")
    
    return state

def generate_expense_response(state: ExpenseState) -> ExpenseState:
    """Generate response message for the driver"""
    
    if state["validation_status"] == "failed":
        error_details = ", ".join(state["extracted_data"]["validation_errors"])
        state["response_message"] = f"❌ **Expense Recording Failed**\n\nIssues found: {error_details}\n\nPlease provide more details or try again with format:\n'Fuel expense ₹1500 at Delhi HP Pump'"
        return state
    
    # Success response
    response = "✅ **Expense Recorded Successfully!**\n\n"
    
    # Add expense emoji based on type
    emoji_map = {
        "fuel": "⛽", "toll": "🛣️", "parking": "🅿️", 
        "maintenance": "🔧", "food": "🍽️", "other": "📝"
    }
    expense_emoji = emoji_map.get(state["expense_type"], "📝")
    
    response += f"{expense_emoji} **Type:** {state['expense_type'].title()}\n"
    response += f"💰 **Amount:** ₹{state['amount']:,.2f}\n"
    
    if state["location"]:
        response += f"📍 **Location:** {state['location']}\n"
    
    if state["vendor_name"]:
        response += f"🏪 **Vendor:** {state['vendor_name']}\n"
    
    response += f"🧾 **Receipt #:** {state['receipt_number']}\n"
    response += f"⏰ **Time:** {state['timestamp']}\n"
    response += f"📊 **Confidence:** {state['extracted_data']['confidence_score']}%\n"
    
    # Add warnings if any
    if state["validation_status"] == "warning":
        warnings = state["extracted_data"]["warnings"]
        response += f"\n⚠️ **Notices:**\n"
        for warning in warnings:
            response += f"• {warning}\n"
    
    response += "\n💡 **Next Steps:**\n"
    response += "• Expense added to your trip record\n"
    response += "• Receipt will be processed for reimbursement\n"
    response += "• Check monthly summary with 'expense report'"
    
    state["response_message"] = response
    return state

# Create the workflow
def create_expense_tracker_workflow():
    """Create LangGraph workflow for expense tracking"""
    
    workflow = StateGraph(ExpenseState)
    
    # Add nodes
    workflow.add_node("parse", parse_expense_message)
    workflow.add_node("validate", validate_expense_data)
    workflow.add_node("save", save_expense_record)
    workflow.add_node("respond", generate_expense_response)
    
    # Add edges
    workflow.add_edge(START, "parse")
    workflow.add_edge("parse", "validate")
    workflow.add_edge("validate", "save")
    workflow.add_edge("save", "respond")
    workflow.add_edge("respond", END)
    
    return workflow.compile()

# Main processing function
def process_expense_message(message: str, driver_id: str = "driver_123") -> Dict:
    """Process an expense tracking message"""
    
    logger.info(f"Processing expense message from driver {driver_id}: {message}")
    
    initial_state = {
        "message": message,
        "driver_id": driver_id,
        "expense_type": "other",
        "amount": 0.0,
        "location": "",
        "receipt_number": "",
        "vendor_name": "",
        "timestamp": "",
        "trip_id": None,
        "extracted_data": {},
        "response_message": "",
        "validation_status": "pending"
    }
    
    workflow = create_expense_tracker_workflow()
    final_state = workflow.invoke(initial_state)
    
    return {
        "type": "expense_tracking",
        "status": "success" if final_state["validation_status"] != "failed" else "failed",
        "expense_type": final_state["expense_type"],
        "amount": final_state["amount"],
        "location": final_state["location"],
        "receipt_number": final_state["receipt_number"],
        "validation_status": final_state["validation_status"],
        "confidence_score": final_state["extracted_data"]["confidence_score"],
        "response": final_state["response_message"],
        "timestamp": final_state["timestamp"]
    }

# Test the agent
if __name__ == "__main__":
    test_messages = [
        "Fuel expense ₹2,500 at Mumbai HP Pump receipt ABC123",
        "Paid toll 350 rupees at Delhi expressway",
        "Food cost Rs. 450 from Punjab Dhaba near Chandigarh", 
        "Maintenance expense 15000 for tyre replacement at Delhi",
        "Parking fee 200 at Bangalore truck terminal",
        "Diesel 3500 from Indian Oil pump"
    ]
    
    for msg in test_messages:
        print(f"\n💰 Expense: {msg}")
        result = process_expense_message(msg)
        print(f"📊 Type: {result['expense_type']}, Amount: ₹{result['amount']}")
        print(f"✅ Status: {result['validation_status']}")
        print(f"🤖 Response:\n{result['response'][:200]}...")
        print("=" * 80)
