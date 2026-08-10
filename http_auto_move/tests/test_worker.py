import math
import unittest

from http_auto_move.http_worker import HttpAutoMoveWorker


class _FakeClient:
    def __init__(self):
        self.calls = []

    def joystick(self, **axes):
        self.calls.append(dict(axes))
        return {"status": True}

    def stop_joystick(self):
        self.calls.append(
            {"move_x": 0, "move_y": 0, "turn_x": 0, "turn_y": 0}
        )
        return {"status": True}


class _FakeManualClient:
    control_base = "http://127.0.0.1:22000"

    def __init__(self):
        self.calls = []

    def raw_request(self, method, path, payload):
        self.calls.append((method, path, payload))
        return {"status": True, "value": "ok"}

    def upload_audio_file(self, payload):
        self.calls.append(("UPLOAD", "/upload/formdata/audio", payload))
        return {"status": True, "taskId": "test"}


class WorkerSequenceTest(unittest.TestCase):
    @staticmethod
    def _pose(pos, yaw_deg):
        return {
            "pos": list(pos),
            "pos_at": 1.0,
            "rpy": [0.0, 0.0, math.radians(yaw_deg)],
            "rpy_at": 1.0,
        }

    def test_connection_type_uses_controller_report(self):
        worker = HttpAutoMoveWorker()
        worker._connection_type = "AP"

        class Client:
            @staticmethod
            def connection_type():
                return "Station"

        self.assertEqual(worker._resolve_connection_type(Client()), "Station")

    def test_drive_repeats_command_and_finishes_with_zero(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._drive_once(
            client,
            "test",
            {"move_x": 0, "move_y": 2000, "turn_x": 0, "turn_y": 0},
            duration=0.03,
            rate_hz=50,
            cycle=1,
            total=1,
        )
        self.assertGreaterEqual(len(client.calls), 4)
        self.assertEqual(client.calls[0]["move_y"], 2000)
        self.assertTrue(all(value == 0 for value in client.calls[-1].values()))

    def test_execute_runs_both_directions_in_one_group(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        logs = []
        worker.log_msg.connect(logs.append)
        worker._execute({
            "name": "前后来回",
            "segments": [
                {"name": "前进", "move_y": 3000, "duration": 0.05},
                {"name": "后退", "move_y": -3000, "duration": 0.05},
            ],
            "repetitions": 1,
            "settle_time": 0.0,
            "rate_hz": 50.0,
            "prepare_action_id": None,
        })
        non_zero = [call for call in client.calls if any(call.values())]
        self.assertTrue(any(call["move_y"] > 0 for call in non_zero))
        self.assertTrue(any(call["move_y"] < 0 for call in non_zero))
        self.assertTrue(all(value == 0 for value in client.calls[-1].values()))
        self.assertTrue(any("[CMD] ▶ 第1组 ↑ 前进" in line for line in logs))
        self.assertTrue(any("[CMD] ▶ 第1组 ↓ 后退" in line for line in logs))
        self.assertTrue(any("摇杆已归零" in line for line in logs))

    def test_translation_and_group_errors_are_formatted_for_log(self):
        start = self._pose([0.0, 0.0, 0.0], 0.0)
        end = self._pose([1.0, 0.1, 0.02], 3.0)
        segment = HttpAutoMoveWorker._segment_error_text(
            "前进",
            {"move_x": 0, "move_y": 3000, "turn_x": 0, "turn_y": 0},
            start,
            end,
        )
        self.assertIn("沿指令位移=+1.0000m", segment)
        self.assertIn("侧向误差=0.1000m", segment)

        group = HttpAutoMoveWorker._group_error_text(
            2, "前后来回", start, end
        )
        self.assertIn("第2组 前后来回 回零误差", group)
        self.assertIn("平面=1.0050m", group)
        self.assertIn("偏航=3.00°", group)

    def test_manual_api_runs_on_current_control_client(self):
        worker = HttpAutoMoveWorker()
        client = _FakeManualClient()
        worker._client = client
        results = []
        worker.manual_api_result.connect(
            lambda ok, description, result: results.append((ok, description, result))
        )
        worker._execute_manual_api({
            "method": "POST",
            "path": "/settings/searchLight",
            "port": 22000,
            "payload": {"open": True},
        })
        self.assertEqual(
            client.calls,
            [("POST", "/settings/searchLight", {"open": True})],
        )
        self.assertTrue(results[0][0])

    def test_manual_api_log_redacts_passwords(self):
        payload = {
            "ssid": "robot",
            "passWd": "secret-password",
            "nested": {"publisherToken": "secret-token"},
        }
        redacted = HttpAutoMoveWorker._redact_payload(payload)
        self.assertEqual(redacted["passWd"], "***")
        self.assertEqual(redacted["nested"]["publisherToken"], "***")
        self.assertEqual(payload["passWd"], "secret-password")

    def test_manual_audio_api_uses_multipart_client(self):
        worker = HttpAutoMoveWorker()
        client = _FakeManualClient()
        worker._client = client
        worker._execute_manual_api({
            "method": "POST",
            "path": "/upload/formdata/audio",
            "port": 22000,
            "payload": {
                "name": "test", "type": "audio",
                "time": "2026-08-10 10:00:00", "file": "/tmp/test.wav",
            },
        })
        self.assertEqual(client.calls[0][0], "UPLOAD")

    def test_rotation_error_and_log_direction_symbol(self):
        worker = HttpAutoMoveWorker()
        start = self._pose([0.0, 0.0, 0.0], 179.0)
        end = self._pose([0.02, 0.0, 0.0], -179.0)
        rotation = worker._segment_error_text(
            "左转",
            {"move_x": 0, "move_y": 0, "turn_x": -3000, "turn_y": 0},
            start,
            end,
        )
        self.assertIn("实际转角=+2.00°", rotation)
        self.assertIn("位置漂移误差=0.0200m", rotation)
        self.assertEqual(
            worker._direction_symbol(
                {"move_x": 0, "move_y": 8000, "turn_x": 0, "turn_y": 0}
            ),
            "↑",
        )
        self.assertEqual(
            worker._direction_symbol(
                {"move_x": 0, "move_y": 0, "turn_x": -8000, "turn_y": 0}
            ),
            "↺",
        )


if __name__ == "__main__":
    unittest.main()
