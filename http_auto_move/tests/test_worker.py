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


class WorkerSequenceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
