import os
from openai import OpenAI
from dotenv import load_dotenv

# Import our custom Earth Engine tools
from tools import get_region_slope, get_land_cover_details

# Load environment variables
load_dotenv()

# Configure OpenAI Client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


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

    # 2. Analyze using OpenAI
    print(f"\nAgent: All GIS data acquired. Analyzing {area_acres} acres with OpenAI...")
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
        import time
        max_retries = 4
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Agent: Retrying report generation (attempt {attempt+1}/{max_retries})...")

                response = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "429" in err_str) and attempt < max_retries - 1:
                    import re
                    match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str)
                    wait_time = int(float(match.group(1))) + 2 if match else 3 ** attempt
                    if wait_time > 15:
                        raise e
                    print(f"OpenAI API error ({err_str[:40]}), retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
    except Exception as e:
        import re
        err_str = str(e)
        if "429" in err_str:
            match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str)
            delay = int(float(match.group(1))) + 1 if match else 60
            return f"### ⏳ OpenAI API Rate Limit Reached\n\nThe AI provider's free-tier token quota has momentarily been exceeded. \n\n**Action required: Please wait ~{delay} seconds** and click Analyze again."
        elif "503" in err_str:
            return f"### 🌐 OpenAI API Server Overloaded\n\nThe OpenAI backend servers are currently experiencing global high demand (503 error).\n\nSpikes are usually temporary. **Action required: Please wait 10-20 seconds** and click Analyze again."
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
