from typing import Dict, List, TypedDict, Optional
from langgraph.graph import StateGraph, START, END
from loguru import logger
import json
import random
from datetime import datetime, timedelta

# State for load finding workflow
class LoadFinderState(TypedDict):
    query: str
    source_location: str
    destination_location: str
    vehicle_type: str
    load_capacity: str
    available_loads: List[Dict]
    matched_loads: List[Dict]
    response_message: str

# Mock load database - in real app this would come from APIs/WhatsApp scraping
MOCK_LOADS = [
    {
        "load_id": "LD001",
        "source": "Delhi",
        "destination": "Mumbai", 
        "material": "Electronics",
        "weight": "10 tons",
        "vehicle_type": "truck",
        "rate": "₹45,000",
        "loading_date": "2025-09-12",
        "urgency": "normal",
        "company": "TechCorp Ltd"
    },
    {
        "load_id": "LD002", 
        "source": "Mumbai",
        "destination": "Bangalore",
        "material": "Textiles",
        "weight": "8 tons", 
        "vehicle_type": "truck",
        "rate": "₹32,000",
        "loading_date": "2025-09-11",
        "urgency": "urgent",
        "company": "Fashion House"
    },
    {
        "load_id": "LD003",
        "source": "Chennai", 
        "destination": "Hyderabad",
        "material": "Auto Parts",
        "weight": "12 tons",
        "vehicle_type": "truck", 
        "rate": "₹28,000",
        "loading_date": "2025-09-13",
        "urgency": "normal",
        "company": "AutoMakers Inc"
    },
    {
        "load_id": "LD004",
        "source": "Delhi",
        "destination": "Kolkata", 
        "material": "FMCG Products",
        "weight": "15 tons",
        "vehicle_type": "truck",
        "rate": "₹52,000", 
        "loading_date": "2025-09-12",
        "urgency": "high",
        "company": "Consumer Goods Ltd"
    },
    {
        "load_id": "LD005",
        "source": "Pune",
        "destination": "Delhi",
        "material": "Machinery",
        "weight": "20 tons",
        "vehicle_type": "trailer",
        "rate": "₹65,000",
        "loading_date": "2025-09-14", 
        "urgency": "normal",
        "company": "Heavy Industries"
    }
]

def parse_load_query(state: LoadFinderState) -> LoadFinderState:
    """Parse the load search query to extract requirements"""
    
    query = state["query"].lower()
    logger.info(f"Parsing load query: {query}")
    
    # Extract source location
    common_cities = ["delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad", "pune", "ahmedabad"]
    
    # Look for "from X to Y" pattern
    if "from" in query and "to" in query:
        parts = query.split("from")[1].split("to")
        if len(parts) >= 2:
            state["source_location"] = parts[0].strip().title()
            state["destination_location"] = parts[1].strip().title()
    
    # Extract vehicle type
    if "truck" in query:
        state["vehicle_type"] = "truck"
    elif "trailer" in query:
        state["vehicle_type"] = "trailer" 
    else:
        state["vehicle_type"] = "any"
    
    # Extract capacity if mentioned
    if "ton" in query:
        words = query.split()
        for i, word in enumerate(words):
            if "ton" in word and i > 0:
                try:
                    capacity = words[i-1]
                    state["load_capacity"] = f"{capacity} tons"
                    break
                except:
                    pass
    
    logger.info(f"Parsed - Source: {state['source_location']}, Dest: {state['destination_location']}, Vehicle: {state['vehicle_type']}")
    return state

def search_available_loads(state: LoadFinderState) -> LoadFinderState:
    """Search for loads matching the criteria"""
    
    logger.info("Searching for matching loads...")
    
    available_loads = []
    
    for load in MOCK_LOADS:
        match_score = 0
        
        # Check source location match
        if state["source_location"]:
            if state["source_location"].lower() in load["source"].lower():
                match_score += 3
        
        # Check destination location match  
        if state["destination_location"]:
            if state["destination_location"].lower() in load["destination"].lower():
                match_score += 3
        
        # Check vehicle type match
        if state["vehicle_type"] != "any":
            if state["vehicle_type"] == load["vehicle_type"]:
                match_score += 2
        
        # Add some randomness for realistic results
        if match_score > 0 or random.random() > 0.7:
            load_copy = load.copy()
            load_copy["match_score"] = match_score
            available_loads.append(load_copy)
    
    # Sort by match score and urgency
    available_loads.sort(key=lambda x: (x["match_score"], x["urgency"] == "urgent"), reverse=True)
    
    state["available_loads"] = available_loads[:5]  # Top 5 matches
    logger.info(f"Found {len(available_loads)} matching loads")
    
    return state

def rank_and_filter_loads(state: LoadFinderState) -> LoadFinderState:
    """Rank loads by profitability and suitability"""
    
    logger.info("Ranking and filtering loads...")
    
    matched_loads = []
    
    for load in state["available_loads"]:
        # Calculate basic profitability score
        rate_value = int(load["rate"].replace("₹", "").replace(",", ""))
        weight_value = float(load["weight"].split()[0])
        
        profitability_score = rate_value / (weight_value * 100)  # Rate per kg approximation
        
        # Add urgency bonus
        urgency_bonus = {"urgent": 1.3, "high": 1.2, "normal": 1.0}.get(load["urgency"], 1.0)
        
        final_score = profitability_score * urgency_bonus
        
        load_copy = load.copy()
        load_copy["profitability_score"] = round(final_score, 2)
        matched_loads.append(load_copy)
    
    # Sort by profitability
    matched_loads.sort(key=lambda x: x["profitability_score"], reverse=True)
    
    state["matched_loads"] = matched_loads
    logger.info(f"Ranked {len(matched_loads)} loads by profitability")
    
    return state

def generate_load_response(state: LoadFinderState) -> LoadFinderState:
    """Generate formatted response with load recommendations"""
    
    if not state["matched_loads"]:
        state["response_message"] = "❌ No loads found matching your criteria. Try different locations or vehicle types."
        return state
    
    response = "🚛 **AVAILABLE LOADS FOUND:**\n\n"
    
    for i, load in enumerate(state["matched_loads"][:3], 1):  # Top 3 loads
        urgency_emoji = {"urgent": "🔥", "high": "⚡", "normal": "📦"}.get(load["urgency"], "📦")
        
        response += f"{urgency_emoji} **Load #{i}**\n"
        response += f"📍 **Route:** {load['source']} → {load['destination']}\n"
        response += f"📦 **Material:** {load['material']} ({load['weight']})\n"
        response += f"💰 **Rate:** {load['rate']}\n"
        response += f"📅 **Loading:** {load['loading_date']}\n"
        response += f"🏢 **Company:** {load['company']}\n"
        response += f"⭐ **Score:** {load['profitability_score']}/10\n"
        response += "─" * 40 + "\n\n"
    
    if len(state["matched_loads"]) > 3:
        response += f"📋 *Found {len(state['matched_loads']) - 3} more loads. Contact for details.*\n\n"
    
    response += "💡 **Next Steps:**\n"
    response += "• Reply with load number to get contact details\n"
    response += "• Say 'book Load #1' to reserve the trip\n"
    response += "• Search again with different criteria anytime"
    
    state["response_message"] = response
    return state

# Create the workflow
def create_load_finder_workflow():
    """Create LangGraph workflow for load finding"""
    
    workflow = StateGraph(LoadFinderState)
    
    # Add nodes
    workflow.add_node("parse_query", parse_load_query)
    workflow.add_node("search_loads", search_available_loads)
    workflow.add_node("rank_loads", rank_and_filter_loads)
    workflow.add_node("generate_response", generate_load_response)
    
    # Add edges
    workflow.add_edge(START, "parse_query")
    workflow.add_edge("parse_query", "search_loads")
    workflow.add_edge("search_loads", "rank_loads")
    workflow.add_edge("rank_loads", "generate_response")
    workflow.add_edge("generate_response", END)
    
    return workflow.compile()

# Main processing function
def process_load_search(query: str, driver_id: str = "driver_123") -> Dict:
    """Process a load search query"""
    
    logger.info(f"Processing load search from driver {driver_id}: {query}")
    
    initial_state = {
        "query": query,
        "source_location": "",
        "destination_location": "",
        "vehicle_type": "any",
        "load_capacity": "",
        "available_loads": [],
        "matched_loads": [],
        "response_message": ""
    }
    
    workflow = create_load_finder_workflow()
    final_state = workflow.invoke(initial_state)
    
    return {
        "type": "load_search",
        "status": "success",
        "query": query,
        "source": final_state["source_location"],
        "destination": final_state["destination_location"],
        "loads_found": len(final_state["matched_loads"]),
        "response": final_state["response_message"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# Test the agent
if __name__ == "__main__":
    test_queries = [
        "Looking for loads from Delhi to Mumbai",
        "Need truck loads from Chennai to any destination", 
        "Searching loads for 15 ton trailer from Pune",
        "Any loads available for immediate pickup"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        result = process_load_search(query)
        print(f"📊 Found: {result['loads_found']} loads")
        print(f"🤖 Response:\n{result['response']}")
        print("=" * 80)
