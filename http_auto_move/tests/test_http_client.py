from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from http_auto_move.http_client import MH4HttpClient, MH4HttpError
from http_auto_move.motion import direction_axes


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
        content_type = request.get_header("Content-type", "")
        if content_type.startswith("multipart/form-data"):
            payload = request.data
        else:
            payload = json.loads(request.data.decode("utf-8")) if request.data else None
        key = (request.get_method(), parsed.path)
        self.requests.append((*key, payload))
        return _Response(self.responses.get(key, {"status": True}))

    def test_address_defaults_to_documented_ports(self):
        client = MH4HttpClient("192.168.1.6")
        self.assertEqual(client.control_base, "http://192.168.1.6:22000")

    def test_connection_and_exchange(self):
        self.responses[("GET", "/connection/type")] = {"value": "Station"}
        self.responses[("GET", "/protocol/exchange")] = {
            "imu": {"rpy": [0, 0, 0]}
        }
        self.assertEqual(self.client.connection_type(), "Station")
        self.client.connect("test", "AP", 1)
        result = self.client.exchange()
        self.assertIn("imu", result)
        self.assertEqual(
            self.requests[1],
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
        with patch("http_auto_move.http_client.time.time", return_value=1234.567):
            self.client.joystick(-50000, 50000, -123, 456)
        self.assertEqual(
            self.requests[-1],
            (
                "POST",
                "/settings/movement/joystickControl",
                {
                    "btn_move": {"x": -32768, "y": 32767},
                    "btn_turn": {"x": -123, "y": 456},
                    "timestamp": 1234567,
                },
            ),
        )

    def test_movement_action(self):
        self.client.movement_action(20)
        self.assertEqual(
            self.requests[-1],
            ("POST", "/settings/movement/action", {"id": 20}),
        )

    def test_raw_request_accepts_top_level_json_array(self):
        self.client.raw_request("POST", "/algs/slam/queryProgressing", ["map1"])
        self.assertEqual(
            self.requests[-1],
            ("POST", "/algs/slam/queryProgressing", ["map1"]),
        )

    def test_raw_request_rejects_full_or_protocol_relative_url(self):
        with self.assertRaises(ValueError):
            self.client.raw_request("GET", "http://example.com/path")
        with self.assertRaises(ValueError):
            self.client.raw_request("GET", "//example.com/path")

    def test_audio_upload_builds_multipart_form(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            audio.write(b"RIFF-test-audio")
            audio.flush()
            result = self.client.upload_audio_file({
                "name": "test",
                "type": "audio",
                "time": "2026-08-10 10:00:00",
                "file": audio.name,
            })
        self.assertTrue(result["status"])
        method, path, body = self.requests[-1]
        self.assertEqual((method, path), ("POST", "/upload/formdata/audio"))
        self.assertIn(b'name="file"', body)
        self.assertIn(b"RIFF-test-audio", body)

    def test_emergency_stop(self):
        self.client.emergency_stop(True)
        self.assertEqual(
            self.requests[-1],
            ("POST", "/settings/emergencyStop", {"value": True}),
        )

    def test_false_status_raises(self):
        self.responses[("POST", "/settings/emergencyStop")] = {"status": False}
        with self.assertRaises(MH4HttpError):
            self.client.emergency_stop(True)


class MotionTest(unittest.TestCase):
    def test_direction_axes(self):
        self.assertEqual(direction_axes("forward", 8000)["move_y"], 8000)
        self.assertEqual(direction_axes("backward", 8000)["move_y"], -8000)
        self.assertEqual(direction_axes("right", 8000)["move_x"], 8000)
        self.assertEqual(direction_axes("rotate_left", 8000)["turn_x"], -8000)

if __name__ == "__main__":
    unittest.main()
