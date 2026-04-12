import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app import create_app
from app.agents.drug_interaction_agent import DrugInteractionAgent
from langchain_core.messages import HumanMessage

app = create_app()
with app.app_context():
    agent = DrugInteractionAgent()
    state = {
        "messages": [HumanMessage(content="Check interactions for Ibuprofen and Warfarin")],
        "patient_id": None,
        "session_id": "test-session",
        "intent": "drug_interaction",
        "context": {},
        "tool_outputs": [],
        "final_response": None,
        "error": None,
    }
    
    print("Invoking DrugInteractionAgent...")
    result = agent.invoke(state)
    
    final = result.get("final_response")
    if final:
        print("\n--- AGENT RESPONSE ---")
        print(f"Safety Rating: {final.get('overall_safety_rating')}")
        print(f"Total Interactions: {final.get('total_interactions')}")
        print(f"Content Preview: {final.get('content')[:200]}...")
        
        if final.get('total_interactions') > 0:
            print("SUCCESS: Interaction detected.")
        else:
            print("FAILURE: No interaction detected.")
            
        if "technical issue" in final.get('content').lower():
            print("FAILURE: Fallback message triggered.")
        else:
            print("SUCCESS: Full analysis performed.")
    else:
        print("FAILURE: No final response.")
