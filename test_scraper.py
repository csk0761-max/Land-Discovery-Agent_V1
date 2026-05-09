import asyncio
from revenue_tools import fetch_chhattisgarh_khasra_details

# Let's use a dummy village code. Wait, the user fetched something. I will just construct one or query the API.
import json
from revenue_tools import get_polygon_owner_info

print(json.dumps(get_polygon_owner_info(
    lat=22.18, lon=82.52, area_acres=10, state_name="Chhattisgarh",
    survey_numbers=["1"],
    admin_hierarchy={
        "district_code": "54",
        "tehsil_code": "10",
        "ri_code": "41",
        "village_code": "007"
    }
), indent=2))
