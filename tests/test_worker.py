import math
import time
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

    def test_boundary_geometry_uses_set_pose_as_oriented_center(self):
        boundary = HttpAutoMoveWorker._boundary_geometry(
            [10.0, 20.0, 0.3], length=4.0, width=2.0, yaw=0.0
        )
        self.assertEqual(boundary["center"], [10.0, 20.0, 0.3])
        expected = (
            [12.0, 21.0, 0.3],
            [12.0, 19.0, 0.3],
            [8.0, 19.0, 0.3],
            [8.0, 21.0, 0.3],
        )
        for actual, wanted in zip(boundary["corners"], expected):
            for value, target in zip(actual, wanted):
                self.assertAlmostEqual(value, target)

    def test_boundary_detection_respects_set_yaw(self):
        boundary = HttpAutoMoveWorker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=math.pi / 2.0
        )
        self.assertFalse(
            HttpAutoMoveWorker._boundary_outside([0.9, 1.9, 0.0], boundary)
        )
        self.assertTrue(
            HttpAutoMoveWorker._boundary_outside([1.01, 0.0, 0.0], boundary)
        )
        self.assertTrue(
            HttpAutoMoveWorker._boundary_outside([0.0, 2.01, 0.0], boundary)
        )

    def test_polygon_boundary_uses_convex_hull_and_area_centroid(self):
        boundary = HttpAutoMoveWorker._polygon_boundary_geometry([
            [2.0, 1.0, 0.3],
            [0.0, 0.0, 0.3],
            [1.0, 0.5, 0.3],  # 内部点不应成为边界顶点
            [0.0, 1.0, 0.3],
            [2.0, 0.0, 0.3],
        ])
        self.assertEqual(boundary["kind"], "polygon")
        self.assertEqual(len(boundary["corners"]), 4)
        self.assertAlmostEqual(boundary["center"][0], 1.0)
        self.assertAlmostEqual(boundary["center"][1], 0.5)
        self.assertAlmostEqual(boundary["length"], 2.0)
        self.assertAlmostEqual(boundary["width"], 1.0)

    def test_polygon_boundary_detection_and_validation(self):
        boundary = HttpAutoMoveWorker._polygon_boundary_geometry([
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [1.0, 2.0, 0.0],
        ])
        self.assertFalse(
            HttpAutoMoveWorker._boundary_outside([1.0, 0.5, 0.0], boundary)
        )
        self.assertFalse(
            HttpAutoMoveWorker._boundary_outside([1.0, 2.0, 0.0], boundary)
        )
        self.assertTrue(
            HttpAutoMoveWorker._boundary_outside([1.9, 1.5, 0.0], boundary)
        )
        validated = HttpAutoMoveWorker._validated_boundary(boundary)
        self.assertEqual(validated["kind"], "polygon")
        self.assertEqual(len(validated["corners"]), 3)

    def test_polygon_boundary_rejects_degenerate_points(self):
        with self.assertRaisesRegex(ValueError, "同一直线"):
            HttpAutoMoveWorker._polygon_boundary_geometry([
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [2.0, 2.0, 0.0],
            ])

    def test_execute_random_patrol_completes_requested_segment_count(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        phases = []

        class FixedRandom:
            @staticmethod
            def random():
                return 0.25

            @staticmethod
            def uniform(_start, _end):
                return 0.6

        def fake_drive(_client, name, axes, duration, rate, cycle, total,
                       *, boundary=None, visualize_command=False):
            phases.append((
                name, axes, duration, rate, cycle, total, boundary,
                visualize_command,
            ))
            return "completed", 0.0

        worker._random = FixedRandom()
        worker._drive_once = fake_drive
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 4000,
            "move_duration": 1.2,
            "repetitions": 3,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(len(phases), 6)
        self.assertTrue(all(phase[1]["turn_x"] == -4000 for phase in phases[::2]))
        self.assertTrue(all(phase[2] == 0.6 for phase in phases[::2]))
        self.assertTrue(all(phase[1]["move_y"] == 4000 for phase in phases[1::2]))
        self.assertTrue(all(phase[2] == 1.2 for phase in phases[1::2]))
        self.assertTrue(all(phase[7] for phase in phases))
        self.assertEqual(finished[-1], "随机巡逻完成")

    def test_random_patrol_returns_to_center_when_turn_starts_outside(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        worker._drive_once = lambda *_args, **_kwargs: ("outside", 1.1)
        recovery_calls = []
        worker._return_to_boundary_center = (
            lambda _client, recovery_boundary, amplitude, turn_amplitude:
            recovery_calls.append((
                recovery_boundary, amplitude, turn_amplitude,
            ))
            or ("reached", 0.03)
        )
        logs = []
        worker.log_msg.connect(logs.append)
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 5000,
            "move_duration": 1.0,
            "repetitions": 1,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(recovery_calls, [(boundary, 5000, 5000)])
        self.assertTrue(any("巡逻转向时检测到越界" in line for line in logs))
        self.assertTrue(any("已回到中心" in line for line in logs))
        self.assertEqual(finished[-1], "随机巡逻完成")

    def test_random_patrol_uses_independent_move_and_turn_speeds(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        phases = []
        worker._random.random = lambda: 0.25
        worker._random.uniform = lambda _start, _end: 0.5
        worker._drive_once = (
            lambda _client, name, axes, *_args, **_kwargs:
            phases.append((name, axes)) or ("completed", 0.0)
        )
        worker._execute({
            "mode": "random_patrol",
            "boundary": worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
            ),
            "move_speed": 5000,
            "turn_speed": 16000,
            "move_duration": 1.0,
            "repetitions": 1,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(phases[0][1]["turn_x"], -16000)
        self.assertEqual(phases[1][1]["move_y"], 5000)

    def test_random_patrol_returns_to_center_when_forward_crosses_boundary(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        drive_results = iter((("completed", 0.0), ("outside", 1.1)))
        worker._drive_once = lambda *_args, **_kwargs: next(drive_results)
        recovery_calls = []
        worker._return_to_boundary_center = (
            lambda _client, recovery_boundary, amplitude, turn_amplitude:
            recovery_calls.append((
                recovery_boundary, amplitude, turn_amplitude,
            ))
            or ("reached", 0.04)
        )
        logs = []
        worker.log_msg.connect(logs.append)
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 4000,
            "move_duration": 1.0,
            "repetitions": 1,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(recovery_calls, [(boundary, 4000, 4000)])
        self.assertTrue(any("巡逻前进时检测到越界" in line for line in logs))
        self.assertEqual(finished[-1], "随机巡逻完成")

    def test_drive_stops_before_command_when_already_outside_boundary(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        with worker._pose_lock:
            worker._latest_position = [1.1, 0.0, 0.0]
            worker._latest_position_at = time.monotonic()
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
        )
        result, center_error = worker._drive_once(
            client,
            "test",
            {"move_x": 0, "move_y": 5000, "turn_x": 0, "turn_y": 0},
            duration=1.0,
            rate_hz=10.0,
            cycle=1,
            total=1,
            boundary=boundary,
        )
        self.assertEqual(result, "outside")
        self.assertAlmostEqual(center_error, 1.1)
        self.assertTrue(all(value == 0 for value in client.calls[-1].values()))
        self.assertFalse(any(call["move_y"] == 5000 for call in client.calls))

    def test_patrol_boundary_check_does_not_require_imu_heading(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        with worker._pose_lock:
            worker._latest_position = [0.0, 0.0, 0.0]
            worker._latest_position_at = time.monotonic()
            worker._latest_http_rpy = None
            worker._latest_http_rpy_at = 0.0
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
        )

        result, _center_error = worker._drive_once(
            client,
            "test",
            {"move_x": 0, "move_y": 2000, "turn_x": 0, "turn_y": 0},
            duration=0.03,
            rate_hz=50.0,
            cycle=1,
            total=1,
            boundary=boundary,
        )

        self.assertEqual(result, "completed")
        self.assertTrue(any(call["move_y"] == 2000 for call in client.calls))

    def test_patrol_forward_command_visualization_follows_current_yaw(self):
        command = HttpAutoMoveWorker._joystick_command_visualization(
            {
                "pos": [1.0, 2.0, 0.0],
                "rpy": [0.0, 0.0, math.pi / 2.0],
            },
            {"move_x": 0, "move_y": 5000, "turn_x": 0, "turn_y": 0},
        )

        self.assertEqual(command["phase"], "move")
        self.assertAlmostEqual(command["current"][0], 1.0)
        self.assertAlmostEqual(command["current"][1], 2.0)
        self.assertAlmostEqual(command["target"][0], 1.0)
        self.assertAlmostEqual(command["target"][1], 2.8)
        self.assertAlmostEqual(command["current_yaw"], 90.0)

    def test_patrol_turn_command_visualization_uses_turn_arc(self):
        command = HttpAutoMoveWorker._joystick_command_visualization(
            {
                "pos": [1.0, 2.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
            },
            {"move_x": 0, "move_y": 0, "turn_x": -5000, "turn_y": 0},
        )

        self.assertEqual(command["phase"], "turn")
        self.assertEqual(command["target"], command["current"])
        self.assertAlmostEqual(command["current_yaw"], 0.0)
        self.assertAlmostEqual(command["target_yaw"], 90.0)

    def test_visualized_drive_emits_command_then_clears_it(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        now = time.monotonic()
        worker._pose_snapshot = lambda: {
            "pos": [0.0, 0.0, 0.0],
            "pos_at": now,
            "rpy": [0.0, 0.0, 0.0],
            "rpy_at": now,
        }
        commands = []
        worker.recovery_command.connect(commands.append)

        result, _center_error = worker._drive_once(
            client,
            "向前巡逻",
            {"move_x": 0, "move_y": 2000, "turn_x": 0, "turn_y": 0},
            duration=0.03,
            rate_hz=50.0,
            cycle=1,
            total=1,
            boundary=worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
            visualize_command=True,
        )

        self.assertEqual(result, "completed")
        self.assertTrue(any(command and command["phase"] == "move"
                            for command in commands))
        self.assertIsNone(commands[-1])

    def test_execute_inserts_return_center_then_continues_pair(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        drive_results = iter((("outside", 1.1), ("completed", 0.0)))
        driven_segments = []
        recovery_calls = []

        def fake_drive(_client, name, _axes, _duration, _rate, _cycle, _total,
                       *, boundary=None):
            driven_segments.append((name, boundary))
            return next(drive_results)

        def fake_recovery(_client, boundary, amplitude):
            recovery_calls.append((boundary, amplitude))
            return "reached", 0.03

        worker._drive_once = fake_drive
        worker._return_to_boundary_center = fake_recovery
        logs = []
        worker.log_msg.connect(logs.append)
        worker._execute({
            "name": "前后来回",
            "segments": [
                {"name": "前进", "move_y": 5000, "duration": 1.0},
                {"name": "后退", "move_y": -5000, "duration": 1.0},
            ],
            "repetitions": 1,
            "settle_time": 0.0,
            "rate_hz": 10.0,
            "prepare_action_id": None,
            "boundary": worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
        })
        self.assertEqual(len(driven_segments), 2)
        self.assertEqual(len(recovery_calls), 1)
        self.assertEqual(recovery_calls[0][1], 5000)
        self.assertTrue(any("插入回中心指令" in line for line in logs))
        self.assertTrue(any("越界回中心完成: 中心误差=0.0300m" in line for line in logs))

    def test_return_center_axes_follow_current_http_yaw(self):
        axes = HttpAutoMoveWorker._axes_to_world_target(
            [0.0, 0.0, 0.0], [0.0, 1.0, 0.0],
            yaw=math.pi / 2.0, amplitude=5000, tolerance=0.05,
        )
        self.assertEqual(axes["move_x"], 0)
        self.assertGreater(axes["move_y"], 0)
        self.assertEqual(axes["turn_x"], 0)

    def test_return_center_turns_before_moving_when_center_is_behind(self):
        axes = HttpAutoMoveWorker._axes_to_world_target(
            [1.0, 0.0, 0.0], [0.0, 0.0, 0.0],
            yaw=0.0, amplitude=5000, tolerance=0.05,
            turn_amplitude=16000,
        )

        self.assertEqual(axes["move_x"], 0)
        self.assertEqual(axes["move_y"], 0)
        self.assertEqual(abs(axes["turn_x"]), 16000)

    def test_return_center_caps_patrol_speed_and_accepts_near_center_timeout(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        captured = {}

        def fake_drive(_client, _boundary, amplitude, tolerance, timeout,
                       *, turn_amplitude=None):
            captured.update(
                amplitude=amplitude,
                turn_amplitude=turn_amplitude,
                tolerance=tolerance,
                timeout=timeout,
            )
            return "timeout", 0.1707

        worker._drive_to_boundary_center = fake_drive
        logs = []
        worker.log_msg.connect(logs.append)
        result, error = worker._return_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
            ),
            amplitude=20000,
        )

        self.assertEqual((result, error), ("reached", 0.1707))
        self.assertEqual(captured["amplitude"], 20000)
        self.assertEqual(captured["turn_amplitude"], 20000)
        self.assertAlmostEqual(captured["tolerance"], 0.15)
        self.assertTrue(any("近中心缓冲区" in line for line in logs))

    def test_return_center_raises_low_speed_above_turn_deadband(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        captured = {}
        worker._drive_to_boundary_center = (
            lambda _client, _boundary, amplitude, _tolerance, _timeout,
            turn_amplitude=None:
            captured.update(
                amplitude=amplitude,
                turn_amplitude=turn_amplitude,
            ) or ("reached", 0.03)
        )

        result, error = worker._return_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
            ),
            amplitude=5000,
        )

        self.assertEqual((result, error), ("reached", 0.03))
        self.assertEqual(captured["amplitude"], 8000)
        self.assertEqual(captured["turn_amplitude"], 8000)

    def test_return_center_does_not_accept_timeout_far_from_center(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._drive_to_boundary_center = (
            lambda *_args, **_kwargs: ("timeout", 0.25)
        )

        result, error = worker._return_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
            ),
            amplitude=20000,
        )

        self.assertEqual((result, error), ("timeout", 0.25))

    def test_return_center_slows_down_near_target(self):
        axes = HttpAutoMoveWorker._axes_to_world_target(
            [0.0, 0.0, 0.0], [0.17, 0.0, 0.0],
            yaw=0.0, amplitude=8000, tolerance=0.15,
        )

        self.assertEqual(axes["move_x"], 0)
        self.assertGreaterEqual(axes["move_y"], 500)
        self.assertLess(axes["move_y"], 2500)

    def test_return_center_logs_command_progress(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        poses = iter((
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ))

        def pose_snapshot():
            now = time.monotonic()
            return {
                "pos": next(poses),
                "pos_at": now,
                "rpy": [0.0, 0.0, 0.0],
                "rpy_at": now,
            }

        worker._pose_snapshot = pose_snapshot
        logs = []
        worker.log_msg.connect(logs.append)
        result, error = worker._drive_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
            amplitude=5000,
            tolerance=0.05,
            timeout=1.0,
        )

        self.assertEqual((result, error), ("reached", 0.0))
        self.assertTrue(any("回中心中" in line for line in logs))
        moving_calls = [call for call in client.calls if any(call.values())]
        self.assertEqual(len(moving_calls), 1)
        self.assertEqual(moving_calls[0]["move_x"], 0)
        self.assertEqual(moving_calls[0]["move_y"], 0)
        self.assertNotEqual(moving_calls[0]["turn_x"], 0)

    def test_return_center_stops_quickly_when_turn_has_no_response(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._RETURN_TURN_STALL_TIMEOUT = 0.03
        worker._RETURN_TURN_PROGRESS = math.radians(3.0)

        def unchanged_pose():
            now = time.monotonic()
            return {
                "pos": [1.0, 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, 0.0],
                "rpy_at": now,
            }

        worker._pose_snapshot = unchanged_pose
        logs = []
        commands = []
        worker.log_msg.connect(logs.append)
        worker.recovery_command.connect(commands.append)
        result, error = worker._drive_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
            amplitude=8000,
            tolerance=0.05,
            timeout=1.0,
        )

        self.assertEqual((result, error), ("turn_unresponsive", 1.0))
        self.assertTrue(any("转向无响应" in line for line in logs))
        self.assertTrue(any(command and command["phase"] == "turn"
                            for command in commands))
        self.assertTrue(all(value == 0 for value in client.calls[-1].values()))

    def test_return_center_pauses_for_stale_imu_then_resumes(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._RETURN_POSE_RECOVERY_TIMEOUT = 0.2
        stopped = []
        worker._safe_stop = lambda _client: stopped.append(True)
        snapshots = 0

        def pose_snapshot():
            nonlocal snapshots
            snapshots += 1
            now = time.monotonic()
            if snapshots < 3:
                return {
                    "pos": [1.0, 0.0, 0.0],
                    "pos_at": now,
                    "rpy": [0.0, 0.0, 0.0],
                    "rpy_at": now - 2.0,
                }
            return {
                "pos": [0.0, 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, 0.0],
                "rpy_at": now,
            }

        worker._pose_snapshot = pose_snapshot
        logs = []
        worker.log_msg.connect(logs.append)
        result, error = worker._drive_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
            amplitude=5000,
            tolerance=0.05,
            timeout=1.0,
        )

        self.assertEqual(result, "reached")
        self.assertEqual(error, 0.0)
        self.assertEqual(client.calls, [])
        self.assertGreaterEqual(len(stopped), 2)
        self.assertTrue(any("回中心暂停" in line for line in logs))
        self.assertTrue(any("回中心数据已恢复" in line for line in logs))

    def test_return_center_fails_when_imu_does_not_recover(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._RETURN_POSE_RECOVERY_TIMEOUT = 0.03
        worker._RETURN_POSE_POLL_INTERVAL = 0.005
        worker._safe_stop = lambda _client: None

        def stale_pose():
            now = time.monotonic()
            return {
                "pos": [1.0, 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, 0.0],
                "rpy_at": now - 2.0,
            }

        worker._pose_snapshot = stale_pose
        result, error = worker._drive_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
            amplitude=5000,
            tolerance=0.05,
            timeout=1.0,
        )

        self.assertEqual(result, "imu_unavailable")
        self.assertEqual(error, 1.0)

    def test_return_center_sensor_wait_honors_user_stop(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()

        def stale_pose():
            now = time.monotonic()
            return {
                "pos": [1.0, 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, 0.0],
                "rpy_at": now - 2.0,
            }

        worker._pose_snapshot = stale_pose
        worker._safe_stop = lambda _client: worker._stop_motion.set()
        result, error = worker._drive_to_boundary_center(
            client,
            worker._boundary_geometry(
                [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
            ),
            amplitude=5000,
            tolerance=0.05,
            timeout=1.0,
        )

        self.assertEqual(result, "stopped")
        self.assertEqual(error, 1.0)


if __name__ == "__main__":
    unittest.main()
