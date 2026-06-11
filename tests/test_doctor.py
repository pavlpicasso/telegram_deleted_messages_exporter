import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from telegram_deleted_messages.doctor import session_file_for, status_line


class DoctorTests(unittest.TestCase):
    def test_session_file_for_adds_session_suffix(self):
        self.assertEqual(
            session_file_for(Path("config/session")),
            Path("config/session.session"),
        )

    def test_session_file_for_keeps_existing_suffix(self):
        self.assertEqual(
            session_file_for(Path("config/session.session")),
            Path("config/session.session"),
        )

    def test_status_line_returns_none(self):
        with redirect_stdout(StringIO()):
            self.assertIsNone(status_line(True, "Check", "ok"))


if __name__ == "__main__":
    unittest.main()
