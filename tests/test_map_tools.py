# ==========================
# File: tests/test_map_tools.py
# ==========================
import requests
import unittest
from unittest.mock import patch, MagicMock
from openstreetmap_server import OpenStreetMapServer


class TestOpenStreetMapServer(unittest.TestCase):
    def setUp(self):
        self.s = OpenStreetMapServer()

    # -------------------------------------------------
    # Test geocode
    # -------------------------------------------------
    @patch("requests.Session.get")
    def test_geocode_ok(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = [
            {"display_name": "Paris, France", "lat": "48.8566", "lon": "2.3522"}
        ]
        mock_get.return_value = mock_resp

        res = self.s.geocode("Paris")
        self.assertEqual(res[0]["display_name"], "Paris, France")
        self.assertAlmostEqual(res[0]["lat"], 48.8566, places=4)

    # -------------------------------------------------
    # Test reverse geocode
    # -------------------------------------------------
    @patch("requests.Session.get")
    def test_reverse_geocode_ok(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"display_name": "Somewhere"}
        mock_get.return_value = mock_resp

        res = self.s.reverse_geocode(48.8566, 2.3522)
        self.assertEqual(res["display_name"], "Somewhere")

    # -------------------------------------------------
    # Test route
    # -------------------------------------------------
    @patch("requests.Session.get")
    def test_route_ok(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = [
            # geocode origin
            [{"display_name": "Paris", "lat": "48.8566", "lon": "2.3522"}],
            # geocode destination
            [{"display_name": "Berlin", "lat": "52.52", "lon": "13.405"}],
            # osrm route
            {"routes": [{"distance": 1050000.0, "duration": 36000.0}]},
        ]
        mock_get.return_value = mock_resp

        res = self.s.route("Paris", "Berlin")
        self.assertIn("distance_km", res)
        self.assertIn("duration_min", res)

    # -------------------------------------------------
    # Test matrix
    # -------------------------------------------------
    @patch("requests.Session.get")
    def test_matrix_ok(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = [
            # geocode Paris
            [{"display_name": "Paris", "lat": "48.8566", "lon": "2.3522"}],
            # geocode Berlin
            [{"display_name": "Berlin", "lat": "52.52", "lon": "13.405"}],
            # osrm table
            {"durations": [[0, 1], [1, 0]], "distances": [[0, 10], [10, 0]]},
        ]
        mock_get.return_value = mock_resp

        res = self.s.matrix(["Paris", "Berlin"])
        self.assertIn("durations_s", res)
        self.assertEqual(res["durations_s"][0][1], 1)

    # -------------------------------------------------
    # Test network error handling
    # -------------------------------------------------
    @patch("requests.Session.get")
    def test_geocode_network_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.RequestException("boom")
        mock_get.return_value = mock_resp

        res = self.s.geocode("Paris")
        self.assertTrue(res and "error" in res[0])


if __name__ == "__main__":
    unittest.main()
