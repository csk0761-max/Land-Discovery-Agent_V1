import unittest

from auth import _resolve_role
from settings import Settings


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            cors_allowed_origins=["http://localhost:5173"],
            api_token="operator-secret",
            admin_token="admin-secret",
        )

    def test_resolve_role_returns_operator_for_api_token(self):
        self.assertEqual(_resolve_role("operator-secret", self.settings), "operator")

    def test_resolve_role_returns_admin_for_admin_token(self):
        self.assertEqual(_resolve_role("admin-secret", self.settings), "admin")

    def test_resolve_role_returns_none_for_unknown_token(self):
        self.assertIsNone(_resolve_role("wrong-secret", self.settings))


if __name__ == "__main__":
    unittest.main()
