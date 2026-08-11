import math
import random
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

    def test_random_patrol_targets_stay_inside_inset_rotated_rectangle(self):
        boundary = HttpAutoMoveWorker._boundary_geometry(
            [3.0, -2.0, 0.3], length=4.0, width=2.0, yaw=math.pi / 3.0
        )
        rng = random.Random(1234)
        for _index in range(100):
            target = HttpAutoMoveWorker._random_boundary_target(
                boundary, 0.2, rng=rng
            )
            self.assertFalse(HttpAutoMoveWorker._boundary_outside(target, boundary))
            forward, left = HttpAutoMoveWorker._boundary_local_position(
                target, boundary
            )
            self.assertLessEqual(abs(forward), 1.8 + 1e-9)
            self.assertLessEqual(abs(left), 0.8 + 1e-9)

    def test_random_patrol_targets_stay_inside_polygon(self):
        boundary = HttpAutoMoveWorker._polygon_boundary_geometry([
            [0.0, 0.0, 0.2],
            [3.0, 0.0, 0.2],
            [2.0, 2.0, 0.2],
            [0.0, 1.0, 0.2],
        ])
        rng = random.Random(4321)
        for _index in range(100):
            target = HttpAutoMoveWorker._random_boundary_target(
                boundary, 0.15, rng=rng
            )
            self.assertFalse(HttpAutoMoveWorker._boundary_outside(target, boundary))

    def test_random_patrol_rejects_margin_that_consumes_range(self):
        boundary = HttpAutoMoveWorker._boundary_geometry(
            [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
        )
        with self.assertRaisesRegex(ValueError, "安全边距"):
            HttpAutoMoveWorker._random_boundary_target(
                boundary, 0.5, rng=random.Random(1)
            )

    def test_random_patrol_target_respects_minimum_distance(self):
        boundary = HttpAutoMoveWorker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        rng = random.Random(12)
        for _index in range(100):
            target = HttpAutoMoveWorker._random_boundary_target(
                boundary,
                0.15,
                current_position=[0.0, 0.0, 0.0],
                minimum_distance=0.5,
                rng=rng,
            )
            self.assertFalse(HttpAutoMoveWorker._boundary_outside(target, boundary))
            self.assertGreaterEqual(math.hypot(target[0], target[1]), 0.5)

    def test_execute_random_patrol_completes_requested_segment_count(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        current = [0.0, 0.0, 0.0]
        endpoints = []

        worker._motion_pose = lambda _client, _label: (
            "ready",
            {"pos": list(current), "rpy": [0.0, 0.0, 0.0]},
        )

        def fake_random_target(
            _boundary, _margin, *, current_position, minimum_distance, rng
        ):
            target_x = 1.8 if float(current_position[0]) <= 0.0 else -1.8
            return [target_x, 0.0, 0.0]

        worker._random_boundary_target = fake_random_target
        worker._turn_to_patrol_target = (
            lambda _client, _boundary, _target, _speed, _tolerance, timeout:
            ("reached", 0.5)
        )

        def fake_drive(_client, _boundary, start, endpoint, _speed,
                       _tolerance, _timeout):
            distance = math.hypot(
                endpoint[0] - start[0], endpoint[1] - start[1]
            )
            endpoints.append(list(endpoint))
            current[:] = endpoint
            return "reached", distance, 0.02

        worker._drive_patrol_segment = fake_drive
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 4000,
            "segment_length": 1.0,
            "repetitions": 3,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(len(endpoints), 3)
        for actual, expected_x in zip(endpoints, (1.0, 0.0, 1.0)):
            self.assertAlmostEqual(actual[0], expected_x)
            self.assertAlmostEqual(actual[1], 0.0)
        self.assertEqual(finished[-1], "随机巡逻完成")

    def test_random_patrol_retries_turn_once_above_yaw_deadband(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        worker._motion_pose = lambda _client, _label: (
            "ready",
            {"pos": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
        )
        worker._random_boundary_target = (
            lambda _boundary, _margin, *, current_position, minimum_distance, rng:
            [1.8, 0.0, 0.0]
        )
        turn_results = iter((("timeout", -8.99), ("reached", -2.0)))
        turn_calls = []

        def fake_turn(*_args, **_kwargs):
            turn_calls.append(True)
            return next(turn_results)

        worker._turn_to_patrol_target = fake_turn
        worker._drive_patrol_segment = (
            lambda _client, _boundary, _start, _endpoint, _speed,
            _tolerance, _timeout: ("reached", 1.0, 0.02)
        )
        logs = []
        worker.log_msg.connect(logs.append)
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 20000,
            "segment_length": 1.0,
            "yaw_deadband": 5.0,
            "repetitions": 1,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(len(turn_calls), 2)
        self.assertTrue(any("归零后补转一次" in line for line in logs))
        self.assertTrue(any("补转完成" in line for line in logs))
        self.assertEqual(finished[-1], "随机巡逻完成")

    def test_random_patrol_continues_with_small_residual_after_retry(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        worker._motion_pose = lambda _client, _label: (
            "ready",
            {"pos": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
        )
        worker._distant_boundary_target = (
            lambda _boundary, _margin, *, current_position, rng:
            ([1.8, 0.0, 0.0], 1.8)
        )
        turn_results = iter((("timeout", 8.79), ("timeout", 8.84)))
        worker._turn_to_patrol_target = lambda *_args, **_kwargs: next(
            turn_results
        )
        drive_calls = []

        def fake_drive(*_args, **_kwargs):
            drive_calls.append(True)
            return "reached", 1.0, 0.02

        worker._drive_patrol_segment = fake_drive
        logs = []
        worker.log_msg.connect(logs.append)
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 20000,
            "segment_length": 1.0,
            "yaw_deadband": 5.0,
            "repetitions": 1,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(len(drive_calls), 1)
        self.assertTrue(any("进入前进阶段继续纠偏" in line for line in logs))
        self.assertEqual(finished[-1], "随机巡逻完成")

    def test_random_patrol_rejects_large_residual_after_retry(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._client = client
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        worker._motion_pose = lambda _client, _label: (
            "ready",
            {"pos": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
        )
        worker._distant_boundary_target = (
            lambda _boundary, _margin, *, current_position, rng:
            ([1.8, 0.0, 0.0], 1.8)
        )
        turn_results = iter((("timeout", 18.0), ("timeout", 16.0)))
        worker._turn_to_patrol_target = lambda *_args, **_kwargs: next(
            turn_results
        )
        drive_calls = []
        worker._drive_patrol_segment = lambda *_args, **_kwargs: (
            drive_calls.append(True) or ("reached", 1.0, 0.02)
        )
        finished = []
        worker.finished_ok.connect(finished.append)
        worker._execute({
            "mode": "random_patrol",
            "boundary": boundary,
            "speed": 20000,
            "segment_length": 1.0,
            "yaw_deadband": 5.0,
            "repetitions": 1,
            "infinite": False,
            "settle_time": 0.0,
            "prepare_action_id": None,
        })

        self.assertEqual(drive_calls, [])
        self.assertIn("转向失败", finished[-1])

    def test_random_patrol_turn_uses_breakaway_pulse_near_target(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=4.0, yaw=0.0
        )
        target_yaw = math.radians(8.8)
        yaws = iter((0.0, target_yaw))

        def pose_snapshot():
            now = time.monotonic()
            return {
                "pos": [0.0, 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, next(yaws)],
                "rpy_at": now,
            }

        worker._pose_snapshot = pose_snapshot
        result, error = worker._turn_to_patrol_target(
            client,
            boundary,
            [math.cos(target_yaw), math.sin(target_yaw), 0.0],
            speed=20000,
            tolerance=math.radians(5.0),
            timeout=2.0,
        )

        commands = [call for call in client.calls if any(call.values())]
        self.assertEqual(result, "reached")
        self.assertAlmostEqual(error, 0.0)
        self.assertEqual(len(commands), 1)
        self.assertEqual(abs(commands[0]["turn_x"]), 10000)
        command_index = client.calls.index(commands[0])
        self.assertTrue(
            all(value == 0 for value in client.calls[command_index + 1].values())
        )

    def test_random_patrol_turn_breakaway_scales_with_selected_speed(self):
        self.assertEqual(HttpAutoMoveWorker._patrol_turn_breakaway(5000), 5000)
        self.assertEqual(HttpAutoMoveWorker._patrol_turn_breakaway(10000), 8000)
        self.assertEqual(HttpAutoMoveWorker._patrol_turn_breakaway(20000), 10000)

    def test_random_patrol_turn_does_not_count_pose_wait_as_active_timeout(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=4.0, yaw=0.0
        )
        poses = iter((
            {"pos": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
            {"pos": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, math.pi / 2.0]},
        ))

        def delayed_motion_pose(_client, _label):
            pose = next(poses)
            if pose["rpy"][2] == 0.0:
                time.sleep(0.02)
            return "ready", pose

        worker._motion_pose = delayed_motion_pose
        result, error = worker._turn_to_patrol_target(
            client,
            boundary,
            [0.0, 1.0, 0.0],
            speed=4000,
            tolerance=math.radians(5.0),
            timeout=0.005,
        )

        self.assertEqual(result, "reached")
        self.assertAlmostEqual(error, 0.0)
        self.assertTrue(any(any(call.values()) for call in client.calls))

    def test_random_patrol_turn_stops_before_command_when_position_is_outside(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        now = time.monotonic()
        worker._pose_snapshot = lambda: {
            "pos": [1.1, 0.0, 0.0],
            "pos_at": now,
            "rpy": [0.0, 0.0, 0.0],
            "rpy_at": now,
        }
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=2.0, width=1.0, yaw=0.0
        )
        result, _error = worker._turn_to_patrol_target(
            client,
            boundary,
            [0.0, 0.0, 0.0],
            speed=5000,
            tolerance=math.radians(5.0),
            timeout=2.0,
        )

        self.assertEqual(result, "outside")
        self.assertTrue(client.calls)
        self.assertFalse(any(any(call.values()) for call in client.calls))

    def test_random_patrol_turns_left_toward_target(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=4.0, yaw=0.0
        )
        yaws = iter((0.0, math.pi / 2.0))

        def pose_snapshot():
            now = time.monotonic()
            return {
                "pos": [0.0, 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, next(yaws)],
                "rpy_at": now,
            }

        worker._pose_snapshot = pose_snapshot
        result, error = worker._turn_to_patrol_target(
            client,
            boundary,
            [0.0, 1.0, 0.0],
            speed=4000,
            tolerance=math.radians(5.0),
            timeout=2.0,
        )

        commands = [call for call in client.calls if any(call.values())]
        self.assertEqual(result, "reached")
        self.assertAlmostEqual(error, 0.0)
        self.assertEqual(len(commands), 1)
        self.assertLess(commands[0]["turn_x"], 0)
        self.assertEqual(commands[0]["move_y"], 0)

    def test_random_patrol_moves_forward_for_segment_length(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        positions = iter((0.0, 0.5, 1.0))

        def pose_snapshot():
            now = time.monotonic()
            return {
                "pos": [next(positions), 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, 0.0],
                "rpy_at": now,
            }

        worker._pose_snapshot = pose_snapshot
        result, traveled, endpoint_error = worker._drive_patrol_segment(
            client,
            boundary,
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            speed=4000,
            tolerance=0.08,
            timeout=2.0,
        )

        commands = [call for call in client.calls if any(call.values())]
        self.assertEqual(result, "reached")
        self.assertAlmostEqual(traveled, 1.0)
        self.assertAlmostEqual(endpoint_error, 0.0)
        self.assertTrue(commands)
        self.assertTrue(all(call["move_y"] > 0 for call in commands))
        self.assertTrue(all(call["move_x"] == 0 for call in commands))

    def test_random_patrol_reduces_forward_speed_until_heading_recovers(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._alive.set()
        worker._stop_motion.wait = lambda _timeout: False
        boundary = worker._boundary_geometry(
            [0.0, 0.0, 0.0], length=4.0, width=2.0, yaw=0.0
        )
        positions = iter((0.0, 1.0))

        def pose_snapshot():
            now = time.monotonic()
            return {
                "pos": [next(positions), 0.0, 0.0],
                "pos_at": now,
                "rpy": [0.0, 0.0, math.radians(8.84)],
                "rpy_at": now,
            }

        worker._pose_snapshot = pose_snapshot
        result, _traveled, _endpoint_error = worker._drive_patrol_segment(
            client,
            boundary,
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            speed=20000,
            tolerance=0.08,
            timeout=2.0,
        )

        commands = [call for call in client.calls if any(call.values())]
        self.assertEqual(result, "reached")
        self.assertEqual(len(commands), 1)
        self.assertGreater(commands[0]["move_y"], 0)
        self.assertLess(commands[0]["move_y"], 15000)
        self.assertGreater(commands[0]["turn_x"], 0)

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

    def test_return_center_caps_patrol_speed_and_accepts_near_center_timeout(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        captured = {}

        def fake_drive(_client, _boundary, amplitude, tolerance, timeout):
            captured.update(
                amplitude=amplitude,
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
        self.assertEqual(captured["amplitude"], 8000)
        self.assertAlmostEqual(captured["tolerance"], 0.15)
        self.assertTrue(any("近中心缓冲区" in line for line in logs))

    def test_return_center_does_not_accept_timeout_far_from_center(self):
        worker = HttpAutoMoveWorker()
        client = _FakeClient()
        worker._drive_to_boundary_center = (
            lambda *_args: ("timeout", 0.25)
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
