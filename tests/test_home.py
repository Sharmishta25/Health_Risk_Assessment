"""Verify the empty patient list can render without a provider call."""

import unittest
import tempfile
from pathlib import Path

from app import create_app


class HomeTest(unittest.TestCase):
    def test_home_page(self):
        with tempfile.TemporaryDirectory() as folder:
            with create_app({"TESTING": True, "DATABASE": str(Path(folder) / "test.db")}).test_client() as client:
                response = client.get("/")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Blood-test risk review", response.data)
