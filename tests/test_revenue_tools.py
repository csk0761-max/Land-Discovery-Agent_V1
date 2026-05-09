import unittest

import revenue_tools


class RevenueToolsTests(unittest.TestCase):
    def test_plot_owner_info_marks_simulated_data(self):
        result = revenue_tools.get_plot_owner_info(27.0, 71.0, "Rajasthan")
        self.assertTrue(result["is_simulated"])
        self.assertEqual(result["data_source"], "simulated")
        self.assertIn("demo", result["warning"].lower())

    def test_polygon_owner_info_requires_admin_selection_for_chhattisgarh(self):
        result = revenue_tools.get_polygon_owner_info(27.0, 71.0, 100.0, "Chhattisgarh")
        self.assertFalse(result["is_simulated"])
        self.assertEqual(result["data_source"], "official_chhattisgarh")
        self.assertTrue(result["requires_admin_selection"])

    def test_polygon_owner_info_uses_uploaded_survey_numbers_when_present(self):
        result = revenue_tools.get_polygon_owner_info(
            27.0,
            71.0,
            12.0,
            "Rajasthan",
            survey_numbers=["101/1", "102/2", "101/1"],
        )
        self.assertEqual(result["status"], "Simulated Survey Ownership Lookup")
        self.assertEqual(result["total_khasras_found"], 2)
        self.assertEqual(result["khasra_records"][0]["survey_no"], "101/1")

    def test_estimate_polygon_area_acres_returns_positive_value(self):
        result = revenue_tools.estimate_polygon_area_acres(
            [
                [27.0, 71.0],
                [27.0, 71.001],
                [27.001, 71.001],
                [27.001, 71.0],
            ]
        )
        self.assertGreater(result, 0)

    def test_extract_select_options_parses_bhunaksha_markup(self):
        html = """
        <select name="level_1" id="level_1">
            <option value="44">44 रायपुर</option>
            <option value="43">43 दुर्ग</option>
        </select>
        """
        result = revenue_tools._extract_select_options(html, "level_1")
        self.assertEqual(result[0]["value"], "44")
        self.assertIn("रायपुर", result[0]["label"])

    def test_extract_select_options_parses_options_without_select_wrapper(self):
        html = """
        <option value="08">08 कुकदूर</option>
        <option value="07">07 कुंडा</option>
        """
        result = revenue_tools._extract_select_options(html, "level_2")
        self.assertEqual(result[0]["value"], "08")
        self.assertIn("कुकदूर", result[0]["label"])

    def test_extract_select_options_matches_select_by_id(self):
        html = """
        <select id="level_2">
            <option value="01">01 कवर्धा</option>
        </select>
        """
        result = revenue_tools._extract_select_options(html, "level_2")
        self.assertEqual(result[0]["value"], "01")
        self.assertIn("कवर्धा", result[0]["label"])

    def test_extract_updatepanel_fragments_extracts_html_from_delta_payload(self):
        delta = "1|#||4|updatePanel|ctl00$ContentPlaceHolder1$UpdatePanel1|<select id='ddlTehsil'><option value='1'>A</option></select>|hiddenField|foo|bar|"
        html = revenue_tools._extract_updatepanel_fragments(delta)
        self.assertIn("ddlTehsil", html)

    def test_fetch_chhattisgarh_khasra_parser_extracts_owner_fields(self):
        html = """
        <span id="lblKhasraID">112139081</span>
        <span id="lblkhsarano">91/1/ख ( 0.0240 हे॰ )</span>
        <span id="lblsinchitbhoomi">0.0000 हे॰</span>
        <span id="lblasinchitbhoomi">0.0240 हे॰</span>
        <span id="lblbasra">91/1/ख</span>
        <span id="lblbhuswami">(1) लीलावती, पति - सियम्बर<br/> जोत का प्रकार - अकेला</span>
        <span id="lblpurvabhuswami">(1)नाम - श्रीमती रिंकी डे</span>
        """
        result = revenue_tools._parse_chhattisgarh_report(html, "91/1/ख")

        self.assertEqual(result["khasra_id"], "112139081")
        self.assertIn("लीलावती", result["owner"])
        self.assertAlmostEqual(result["area_hectare"], 0.0240)
        self.assertEqual(result["khasra_no"], "91/1/ख")


if __name__ == "__main__":
    unittest.main()
