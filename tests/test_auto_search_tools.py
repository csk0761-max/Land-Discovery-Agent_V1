import unittest

from auto_search_tools import _calculate_gss_capacity


class AutoSearchToolsTests(unittest.TestCase):
    def test_calculate_gss_capacity_handles_common_voltage_formats(self):
        self.assertEqual(_calculate_gss_capacity("220000;132000"), 500)
        self.assertEqual(_calculate_gss_capacity("220 kV"), 500)
        self.assertEqual(_calculate_gss_capacity(""), 50)

    def test_calculate_gss_capacity_handles_high_voltage_levels(self):
        self.assertEqual(_calculate_gss_capacity("765000"), 2000)
        self.assertEqual(_calculate_gss_capacity("400000"), 1000)


if __name__ == "__main__":
    unittest.main()
