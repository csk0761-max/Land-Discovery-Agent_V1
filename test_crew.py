import os
from dotenv import load_dotenv
from crew_manager import run_premium_expert_analysis

load_dotenv()

# Simulated Data for Testing
mock_geodata = {
    "site": {"location": "Test Site, Rajasthan"},
    "technical": {
        "slope_deg": 4.5,
        "grid_proximity_proxy_km": 1.2,
        "substation_reference": "Test Substation 220kV"
    },
    "premium_intelligence": {
        "hydrology": {"risk_level": "Medium"},
        "grading": {"total_est_lakhs": 25.5}
    }
}

print("🚀 Starting CrewAI Expert Meeting Test...")
print("------------------------------------------")

try:
    verdict = run_premium_expert_analysis(mock_geodata)
    print("\n✅ TEST SUCCESSFUL!")
    print("\n--- EXPERT VERDICT ---")
    print(verdict)
except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
