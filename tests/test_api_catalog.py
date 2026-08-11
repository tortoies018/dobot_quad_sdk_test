import unittest

from http_auto_move.api_catalog import ENDPOINTS


class ApiCatalogTest(unittest.TestCase):
    def test_catalog_contains_all_documented_method_path_pairs(self):
        keys = {(endpoint.method, endpoint.path) for endpoint in ENDPOINTS}
        self.assertEqual(len(keys), len(ENDPOINTS))
        self.assertGreaterEqual(len(ENDPOINTS), 110)
        self.assertIn(("POST", "/settings/movement/joystickControl"), keys)
        self.assertIn(("GET", "/settings/version"), keys)
        self.assertIn(("POST", "/algs/slam/startSinglePointPatrol"), keys)
        self.assertIn(("GET", "/algs/settings/movement/speedRatio"), keys)

    def test_algorithm_routes_use_22002(self):
        for endpoint in ENDPOINTS:
            self.assertIn(endpoint.method, ("GET", "POST"))
            self.assertTrue(endpoint.path.startswith("/"))
            expected_port = 22002 if endpoint.path.startswith("/algs/") else 22000
            self.assertEqual(endpoint.port, expected_port)


if __name__ == "__main__":
    unittest.main()
