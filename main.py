import os
from google import genai
from dotenv import load_dotenv

# Import our custom Earth Engine tools
from tools import get_region_slope, get_land_cover_details

# Load environment variables
load_dotenv()

# Configure Google GenAI Client
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def agent_evaluate_parcel(lat: float, lon: float, area_acres: float) -> str:
    """
    1. Calls Earth Engine to get real GIS parameters for the given coordinates.
    2. Passes the parameters to the LLM to analyze land suitability.
    """
    print(f"Agent: Connecting to Earth Engine for coordinates ({lat}, {lon})...")
    
    # 1. Gather Data from Earth Engine Tools
    try:
        slope = get_region_slope(lat, lon)
        print(f" -> Grabbed Slope: {slope:.2f}°")
        
        land_type, has_forest = get_land_cover_details(lat, lon)
        print(f" -> Grabbed Land Cover: {land_type} (Forest Present: {has_forest})")
    except Exception as e:
        return f"Error connecting to Google Earth Engine: {e}"

    # 2. Analyze using Gemini
    print(f"\nAgent: All GIS data acquired. Analyzing {area_acres} acres with Gemini AI...")
    prompt = f"""
    You are an expert Land Discovery and GIS Agent. Your task is to interpret GIS outputs for a specific land parcel and evaluate its suitability for a Solar Project.

    Here are the actual GIS outputs pulled from Google Earth Engine for the parcel:
    - Coordinates: {lat}, {lon}
    - Slope: {slope:.2f} degrees
    - Land Type: {land_type}
    - Forest Present: {str(has_forest).lower()}
    - Area: {area_acres} acres

    Apply the following exact logic to determine suitability:
    IF slope < 5 AND land type = barren AND forest = false AND area > 500
    THEN Solar Suitability = HIGH.
    Otherwise, evaluate the specific constraints and assign a suitable rating (e.g., MEDIUM, LOW, NOT SUITABLE).

    Based on these inputs, please produce the following three sections:
    1. Feasibility Summary
    2. Risk Analysis
    3. Developer-Ready Report
    
    Ensure the output is highly professional, formatted in Markdown, and ready for a developer or stakeholder to read.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error generating report: {e}"

if __name__ == "__main__":
    # Test 1: Ideal Solar Location (Barren desert in Rajasthan, India)
    lat1, lon1 = 27.0238, 71.9213 
    area1 = 600.0 # acres

    # Test 2: Poor Solar Location (Steppe/Mountain in Himachal)
    lat2, lon2 = 32.2396, 77.1887
    area2 = 200.0

    print("=== SCENARIO 1: Testing potential Desert Site ===")
    report1 = agent_evaluate_parcel(lat1, lon1, area1)
    print("\n" + report1)
    
    print("\n\n" + "="*50 + "\n\n")

    print("=== SCENARIO 2: Testing potential Mountain Site ===")
    report2 = agent_evaluate_parcel(lat2, lon2, area2)
    print("\n" + report2)
