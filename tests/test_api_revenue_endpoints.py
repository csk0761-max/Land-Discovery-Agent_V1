import unittest

from fastapi.testclient import TestClient

from api import app


class RevenueApiEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_survey_ownership_endpoint_returns_simulated_records(self):
        response = self.client.post(
            "/revenue/survey-ownership",
            json={"state": "Rajasthan", "survey_numbers": ["101/1", "102/2", "101/1"]},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_simulated"])
        self.assertEqual(data["data_source"], "simulated")
        self.assertEqual(data["total_khasras_found"], 2)
        self.assertEqual(len(data["khasra_records"]), 2)


if __name__ == "__main__":
    unittest.main()

