import unittest

from settings import _split_csv


class SettingsTests(unittest.TestCase):
    def test_split_csv_discards_blanks_and_whitespace(self):
        self.assertEqual(
            _split_csv(" http://localhost:5173, ,http://127.0.0.1:5173 "),
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        )


if __name__ == "__main__":
    unittest.main()
