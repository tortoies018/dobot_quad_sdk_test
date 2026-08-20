from __future__ import annotations

import unittest

from http_auto_move.video_panel import VIDEO_STREAMS, video_stream_url


class VideoPanelTest(unittest.TestCase):
    def test_streams_are_front_and_rear_only(self):
        self.assertEqual(
            VIDEO_STREAMS,
            (("前置画面", "camera1"), ("后置画面", "camera2")),
        )

    def test_robot_rtsp_url(self):
        self.assertEqual(
            video_stream_url("10.30.12.111", "camera1").toString(),
            "rtsp://10.30.12.111:8554/camera1",
        )

    def test_ipv6_rtsp_url(self):
        self.assertEqual(
            video_stream_url("2001:db8::1", "camera2").toString(),
            "rtsp://[2001:db8::1]:8554/camera2",
        )

    def test_rejects_unknown_stream(self):
        with self.assertRaises(ValueError):
            video_stream_url("10.30.12.111", "depth")


if __name__ == "__main__":
    unittest.main()
