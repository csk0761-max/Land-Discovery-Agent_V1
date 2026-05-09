import os
import json
import logging
from openai import OpenAI
import rag_manager

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def extract_grid_data(unstructured_text: str) -> dict:
    prompt = f"""
    You are a Grid Infrastructure Data Extractor.
    Extract the following information from the provided text about Grid Substations (GSS).
    Return ONLY a valid JSON array of objects, with no markdown formatting.
    If multiple substations are mentioned, return an object for each.
    
    Format for each object:
    [{{
        "gss_name": "Name of the substation",
        "latitude": 0.0,
        "longitude": 0.0,
        "capacity_mw": 0.0,
        "evacuation_voltage_kv": 0.0,
        "line_route_details": "Description of the line route",
        "line_coordinates": [[lat, lon], [lat, lon]]
    }}]
    
    If any field is missing or cannot be determined, use null or 0.0 or empty strings or [] for arrays. The line_coordinates is for drawing the actual line routes on a map - if any coordinates for the route are given, format them as [lat, lon] pairs. 
    Do not wrap the JSON in ```json blocks.
    
    Raw Text to parse:
    {unstructured_text}
    """
    try:
        import time
        max_retries = 4
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logging.info(f"Agent: Retrying data extraction (attempt {attempt+1}/{max_retries})...")

                response = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "429" in err_str) and attempt < max_retries - 1:
                    import re
                    match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str)
                    wait_time = int(float(match.group(1))) + 2 if match else 3 ** attempt
                    if wait_time > 15:
                        raise e
                    logging.warning(f"OpenAI API error ({err_str[:40]}), retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
        
        text = response.choices[0].message.content.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
            
        parsed_data = json.loads(text.strip())
        
        if isinstance(parsed_data, dict):
            parsed_data = [parsed_data]
            
        for item in parsed_data:
            rag_manager.add_structured_gss_data(item)
            
        return {"success": True, "extracted": parsed_data}
    except Exception as e:
        logging.error(f"Error extracting grid data: {e}")
        return {"success": False, "error": str(e), "extracted": []}
