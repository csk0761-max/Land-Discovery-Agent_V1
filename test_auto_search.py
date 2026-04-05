import sys
sys.path.append('.')
from auto_search_agent import agent_auto_search

try:
    print("Running Auto Search Agent for Solar in Rajasthan, Jodhpur...")
    result = agent_auto_search(
        state="Rajasthan",
        district="Jodhpur",
        project_type="solar",
        capacity_mw=100.0,
        area_acres=500.0,
        top_n=3
    )
    print("\n--- REPORT ---")
    print(result['report'])
    print("\n--- CANDIDATES ---")
    for c in result['candidates']:
        print(f"Rank {c.get('rank')}: Lat {c['lat']}, Lon {c['lon']}, Score {c['score']}")
except Exception as e:
    print("Error:", e)
