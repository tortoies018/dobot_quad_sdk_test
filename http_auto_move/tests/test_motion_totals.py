import unittest

from http_auto_move.motion_totals import MotionTotals


class MotionTotalsTest(unittest.TestCase):
    def test_accumulates_planar_distance_and_elapsed_time(self):
        totals = MotionTotals()
        totals.start(10.0, [0.0, 0.0, 1.0])
        totals.observe_position([3.0, 4.0, 8.0])
        totals.observe_position([6.0, 8.0, -3.0])

        self.assertAlmostEqual(totals.distance_m, 10.0)
        self.assertAlmostEqual(totals.elapsed(12.5), 2.5)

        totals.stop(15.0)
        self.assertFalse(totals.running)
        self.assertAlmostEqual(totals.elapsed_s, 5.0)
        self.assertAlmostEqual(totals.elapsed(99.0), 5.0)

    def test_first_position_after_start_is_only_the_baseline(self):
        totals = MotionTotals()
        totals.start(1.0)
        totals.observe_position([5.0, 6.0, 0.0])
        self.assertEqual(totals.distance_m, 0.0)

        totals.observe_position([5.3, 6.4, 10.0])
        self.assertAlmostEqual(totals.distance_m, 0.5)

    def test_new_start_resets_previous_totals(self):
        totals = MotionTotals()
        totals.start(1.0, [0.0, 0.0])
        totals.observe_position([1.0, 0.0])
        totals.stop(3.0)

        totals.start(10.0, [4.0, 4.0])
        self.assertEqual(totals.distance_m, 0.0)
        self.assertEqual(totals.elapsed_s, 0.0)
        self.assertEqual(totals.elapsed(10.0), 0.0)


if __name__ == "__main__":
    unittest.main()
