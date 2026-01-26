import os
import unittest


class TestAsyncWinRM(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.endpoint = os.getenv("WINRM_ENDPOINT", "http://127.0.0.1:5985")
        self.username = os.getenv("WINRM_USERNAME", "Administrator")
        self.password = os.getenv("WINRM_PASSWORD", "password")
        print("asyncio stuff stuff")

    async def test_cool(self):
        print("cool test")
        self.assertEqual(1, 1)
