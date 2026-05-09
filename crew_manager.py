import os
from crewai import Agent, Task, Crew, Process

def run_premium_expert_analysis(geodata: dict):
    """
    Specialized CrewAI committee following the user's specific architecture:
    Land Scout, Technical Feasibility, Risk, and Financial.
    """
    model = "gpt-4o-mini"
    geo = geodata.get('geo_intelligence', {})

    # 1. Specialized Agents
    land_scout = Agent(
        role='Land Scout Specialist',
        goal='Analyze parcel suitability based on substation proximity, size, and connectivity.',
        backstory='Expert in site selection. You evaluate if the parcel is ideally positioned near infrastructure and fits the required size and zoning profile.',
        verbose=True,
        allow_delegation=False,
        llm=model
    )

    tech_feasibility = Agent(
        role='Technical Feasibility Agent',
        goal='Use GEE data to check slope, irradiation, and land type suitability.',
        backstory='Remote sensing specialist. You interpret Google Earth Engine signals to validate the technical potential for solar/wind development.',
        verbose=True,
        allow_delegation=False,
        llm=model
    )

    risk_agent = Agent(
        role='Risk Agent',
        goal='Flag forest proximity, water bodies, habitation risk, and title complexity patterns.',
        backstory='Environmental and legal risk auditor. You identify "project killers" including biodiversity issues, flood risks, and encroachment.',
        verbose=True,
        allow_delegation=False,
        llm=model
    )

    financial_agent = Agent(
        role='Financial Agent',
        goal='Estimate land cost, evacuation cost, and overall IRR impact.',
        backstory='Project finance modeler. You translate technical/risk findings into a commercial bankability verdict.',
        verbose=True,
        allow_delegation=True,
        llm=model
    )

    # 2. Specialized Tasks
    task_scouting = Task(
        description=f"""Analyze the site selection merits:
        - Interconnection: {geodata['technical']['substation_reference']} at {geodata['technical']['grid_proximity_proxy_km']} km
        - Size: {geodata['site']['area_acres']} acres
        Evaluate if this parcel fits the "Sweet Spot" for development near existing substations.""",
        expected_output="A report on site positioning and interconnection logistics.",
        agent=land_scout
    )

    task_feasibility = Task(
        description=f"""Perform GEE-based technical audit:
        - Slope Stats: {geo.get('terrain', {}).get('avg_slope_deg')}° avg, {geo.get('terrain', {}).get('max_slope_deg')}° max
        - Irradiation (GHI): {geodata['technical']['solar_ghi_kwh_m2_day']} kWh/m2/day
        - Land Type: {geo.get('land_use', {}).get('primary_class')}
        Determine technical viability based on resource and terrain data.""",
        expected_output="A technical feasibility summary based on satellite telemetry.",
        agent=tech_feasibility
    )

    task_risk = Task(
        description=f"""Flag critical development risks:
        - Forest/Greenery: {geodata['technical']['has_forest']}
        - Water/Hydrology: {geodata['premium_intelligence']['hydrology']['risk_level']} (Occurrence: {geo.get('hydrology', {}).get('surface_water_occurrence_pct')}%)
        - Habitation/Encroachment: {geo.get('change_detection', {}).get('remark')}
        Assess proximity to forest zones, water bodies, and any habitation/encroachment patterns.""",
        expected_output="A comprehensive risk audit flagging environmental and legal hurdles.",
        agent=risk_agent
    )

    task_finance = Task(
        description=f"""Model the financial feasibility and perform a Developer IC Simulation:
        - Grading Cost: ₹{geodata['premium_intelligence']['grading']['total_est_lakhs']} Lakhs
        - Evacuation Impact: Based on {geodata['technical']['grid_proximity_proxy_km']}km Gen-Tie
        - Resource Quality: {geodata['financial']['specific_yield_kwh_kw_year']} kWh/kW/yr
        
        Calculate a "Developer IC Simulation" result:
        Provide a specific probability (%) of Investment Committee (IC) approval based on evacuation risk, land patterns, and terrain. 
        Format as: "Based on [Factors], this site has a [X]% probability of IC approval."
        Then provide the final Go/No-Go verdict.""",
        expected_output="A simulated IC verdict with a specific approval probability percentage and final investment thesis.",
        agent=financial_agent
    )

    # 3. Assemble and Execute
    crew = Crew(
        agents=[land_scout, tech_feasibility, risk_agent, financial_agent],
        tasks=[task_scouting, task_feasibility, task_risk, task_finance],
        process=Process.sequential,
        verbose=True
    )

    result = crew.kickoff()
    return str(result)
