import unittest

from agent import build_parcel_analysis_context, build_parcel_report_prompt


class AgentContextTests(unittest.TestCase):
    def test_build_parcel_analysis_context_marks_grounded_fields(self):
        context = build_parcel_analysis_context(
            lat=27.0,
            lon=71.0,
            area_acres=600.0,
            slope=2.5,
            land_type="barren",
            has_forest=False,
            ghi=5.8,
            wind=4.2,
            env_risk=False,
            grid_dist=8.5,
            img_url="https://example.com/satellite.png",
            slope_heatmap="https://example.com/slope.png",
            solar_heatmap="https://example.com/solar.png",
            land_cover_map="https://example.com/cover.png",
            gss_info="Bhadla GSS (Distance: 7 km)",
            substation_dist="7",
            roi_data={
                "capacity_mw": 120.0,
                "annual_yield_mwh": 220000.0,
                "capex_cr": 540.0,
                "revenue_annual_lakhs": 4400.0,
                "payback_years": 8.2,
                "currency": "INR",
            },
            location_details={
                "full_address": "Bhadla, Rajasthan, India",
                "village": "Bhadla",
                "tehsil": "Phalodi",
                "district": "Jodhpur",
                "state": "Rajasthan",
            },
            revenue_data={
                "portal": "Apna Khata",
                "status": "Simulated Spatial Intersection",
                "data_source": "simulated",
                "is_simulated": True,
                "warning": "Simulated cadastral data for demo use only.",
                "total_khasras_found": 2,
                "khasra_records": [{"khasra_no": "1/1", "owner": "Demo Owner", "area_acres": 50.0, "land_type": "Banjar"}],
            },
        )

        self.assertEqual(context["site"]["jurisdiction"]["village"], "Bhadla")
        self.assertEqual(context["technical"]["substation_reference"], "Bhadla GSS (Distance: 7 km)")
        self.assertTrue(context["cadastral"]["is_simulated"])
        self.assertGreaterEqual(context["technical"]["project_suitability_score"], 0)

    def test_build_parcel_report_prompt_embeds_structured_facts(self):
        context = {
            "site": {"location": "Bhadla, Rajasthan", "area_acres": 600.0},
            "technical": {
                "project_suitability_score": 88,
                "slope_deg": 2.5,
                "solar_ghi_kwh_m2_day": 5.8,
                "wind_speed_m_s": 4.2,
                "land_type": "barren",
                "substation_reference": "Bhadla GSS",
            },
            "financial": {
                "estimated_capacity_mw": 120.0,
                "estimated_annual_yield_mwh": 220000.0,
                "estimated_capex_cr": 540.0,
                "estimated_annual_revenue_lakhs": 4400.0,
                "simple_payback_years": 8.2,
            },
            "raster_assets": {
                "satellite_image_url": "https://example.com/satellite.png",
                "slope_heatmap_url": "https://example.com/slope.png",
                "solar_heatmap_url": "https://example.com/solar.png",
                "land_cover_map_url": "https://example.com/cover.png",
            },
            "cadastral": {
                "portal": "Apna Khata",
                "status": "Simulated Spatial Intersection",
                "data_source": "simulated",
                "is_simulated": True,
                "warning": "Simulated cadastral data for demo use only.",
            },
        }

        prompt = build_parcel_report_prompt(context, "April 09, 2026 at 10:00 AM")

        self.assertIn("STRUCTURED ANALYSIS FACTS", prompt)
        self.assertIn('"project_suitability_score": 88', prompt)
        self.assertIn("demo-only", prompt)


if __name__ == "__main__":
    unittest.main()
