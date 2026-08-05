import os
import tempfile
import unittest

from app import app


class RenderRootRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_root_route_serves_index_from_app_directory(self):
        original_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                response = self.client.get('/')
        finally:
            os.chdir(original_cwd)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)


if __name__ == '__main__':
    unittest.main()
