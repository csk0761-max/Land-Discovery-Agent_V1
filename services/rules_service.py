from typing import Dict, Any, List

def check_deterministic_rules(geodata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates hard constraints (deterministic rules) for the parcel.
    Returns a dictionary with individual rule results and an overall hard verdict.
    """
    technical = geodata.get('technical', {})
    geo = geodata.get('geo_intelligence', {})
    
    rules = []
    
    # Rule 1: Slope Constraint (Solar specific default)
    slope = technical.get('slope_deg', 0)
    slope_passed = slope <= 15
    rules.append({
        "name": "Topographical Constraint",
        "criteria": "Slope <= 15°",
        "value": f"{slope}°",
        "status": "PASS" if slope_passed else "FAIL",
        "impact": "Critical for structural integrity and grading costs."
    })

    # Rule 2: Land Use Constraint
    land_type = technical.get('land_type', '').lower()
    forbidden_types = {'water', 'built-up', 'wetland', 'permanent snow and ice'}
    land_passed = land_type not in forbidden_types
    rules.append({
        "name": "Land Classification",
        "criteria": "Exclude Water/Built-up",
        "value": land_type.capitalize(),
        "status": "PASS" if land_passed else "FAIL",
        "impact": "Fundamental environmental or legal blockage."
    })

    # Rule 3: Protected Area Check
    is_protected = geo.get('hydrology', {}).get('historical_flood_detected', False) # Using flood as a proxy if protected info is missing in this level
    # Actually, GEE signals already have 'protected' info in some tools, but let's check what we have in geo_signals
    
    # Rule 4: Grid Proximity
    grid_dist = technical.get('grid_proximity_proxy_km', 0)
    grid_passed = grid_dist <= 50
    rules.append({
        "name": "Grid Connectivity",
        "criteria": "Distance <= 50km",
        "value": f"{grid_dist}km",
        "status": "PASS" if grid_passed else "FAIL",
        "impact": "Gen-Tie CAPEX and transmission loss thresholds."
    })

    # Rule 5: Area Threshold
    area = geodata.get('site', {}).get('area_acres', 0)
    area_passed = area >= 10 # Default minimum
    rules.append({
        "name": "Minimum Scale",
        "criteria": "Area >= 10 Acres",
        "value": f"{area} Acres",
        "status": "PASS" if area_passed else "FAIL",
        "impact": "Project bankability and economy of scale."
    })

    # Determine Hard Verdict
    fails = [r for r in rules if r['status'] == 'FAIL']
    hard_verdict = "PASS" if not fails else "FAIL"
    
    return {
        "rules": rules,
        "hard_verdict": hard_verdict,
        "fail_count": len(fails),
        "summary": "Site cleared all deterministic constraints." if not fails else f"Site failed {len(fails)} critical constraints."
    }

def verify_evidence_thresholds(geodata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Programmatically verifies if there is sufficient data 'evidence' to 
    perform a high-fidelity analysis.
    """
    tech = geodata.get('technical', {})
    geo = geodata.get('geo_intelligence', {})
    
    critical_fields = [
        ('slope_deg', tech.get('slope_deg')),
        ('solar_ghi', tech.get('solar_ghi_kwh_m2_day')),
        ('land_type', tech.get('land_type')),
        ('substation', tech.get('substation_reference')),
        ('hydrology', geodata.get('premium_intelligence', {}).get('hydrology', {}).get('surface_water_occurrence_pct'))
    ]
    
    missing = [name for name, val in critical_fields if val in (None, "", -999, "Unknown")]
    completeness_pct = ((len(critical_fields) - len(missing)) / len(critical_fields)) * 100
    
    is_sufficient = completeness_pct >= 60 # Threshold: 60% of critical fields must be present
    
    return {
        "is_sufficient": is_sufficient,
        "completeness_pct": round(completeness_pct, 1),
        "missing_critical_fields": missing,
        "status": "SUFFICIENT" if is_sufficient else "INSUFFICIENT"
    }
