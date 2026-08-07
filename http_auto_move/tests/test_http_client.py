from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from http_auto_move.http_client import MH4HttpClient, MH4HttpError
from http_auto_move.motion import direction_axes, scaled_duration


class _Response:
    def __init__(self, value):
        self._body = json.dumps(value).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class MH4HttpClientTest(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.responses = {}
        self.urlopen_patch = patch(
            "http_auto_move.http_client.urlopen", side_effect=self._urlopen
        )
        self.urlopen_patch.start()
        self.addCleanup(self.urlopen_patch.stop)
        self.client = MH4HttpClient("http://127.0.0.1:22000", timeout=1)

    def _urlopen(self, request, timeout):
        parsed = urlsplit(request.full_url)
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        key = (request.get_method(), parsed.path)
        self.requests.append((*key, payload))
        return _Response(self.responses.get(key, {"status": True}))

    def test_address_defaults_to_documented_ports(self):
        client = MH4HttpClient("192.168.1.6")
        self.assertEqual(client.control_base, "http://192.168.1.6:22000")
        self.assertEqual(client.algorithm_base, "http://192.168.1.6:22002")

    def test_connection_and_exchange(self):
        self.responses[("GET", "/protocol/exchange")] = {
            "imu": {"rpy": [0, 0, 0]}
        }
        self.client.connect("test", "AP", 1)
        result = self.client.exchange()
        self.assertIn("imu", result)
        self.assertEqual(
            self.requests[0],
            (
                "POST",
                "/connection/state",
                {
                    "currentClient": 1,
                    "clientName": "test",
                    "connectionType": "AP",
                },
            ),
        )

    def test_joystick_payload_is_clamped(self):
        self.client.joystick(-50000, 50000, -123, 456)
        self.assertEqual(
            self.requests[-1],
            (
                "POST",
                "/settings/movement/joystickControl",
                {
                    "btn_move": {"x": -32768, "y": 32767},
                    "btn_turn": {"x": -123, "y": 456},
                },
            ),
        )

    def test_emergency_and_speed_ratio(self):
        self.client.emergency_stop(True)
        self.client.set_speed_ratio(200)
        self.assertEqual(
            self.requests[-2:],
            [
                ("POST", "/settings/emergencyStop", {"value": True}),
                (
                    "POST",
                    "/algs/settings/movement/speedRatio",
                    {"ratio": 100},
                ),
            ],
        )

    def test_false_status_raises(self):
        self.responses[("POST", "/settings/emergencyStop")] = {"status": False}
        with self.assertRaises(MH4HttpError):
            self.client.emergency_stop(True)


class MotionTest(unittest.TestCase):
    def test_direction_axes(self):
        self.assertEqual(direction_axes("forward", 8000)["move_y"], -8000)
        self.assertEqual(direction_axes("right", 8000)["move_x"], 8000)
        self.assertEqual(direction_axes("rotate_left", 8000)["turn_x"], -8000)

    def test_duration_uses_amplitude_fraction(self):
        self.assertAlmostEqual(scaled_duration(1.0, 1.0, 32767), 1.0)
        self.assertAlmostEqual(scaled_duration(1.0, 1.0, 16384), 32767 / 16384)


if __name__ == "__main__":
    unittest.main()
