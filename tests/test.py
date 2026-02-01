import os
import socket
import unittest

from asyncwinrm.auth.spnego import negotiate, kerberos
from asyncwinrm.client.winrm import WinRMClient


def _get_client():
    endpoint = os.getenv("WINRM_ENDPOINT", "172.16.17.137")
    method = os.getenv("WINRM_AUTH_METHOD", "negotiate")

    username = os.getenv("WINRM_AUTH_USERNAME", "Administrator")
    password = os.getenv("WINRM_AUTH_PASSWORD", "password")

    if method == "kerberos":
        realm = os.getenv("WINRM_AUTH_REALM", "")
        address = os.getenv("WINRM_AUTH_ADDRESS", "127.0.0.1")
        hostname = os.getenv("WINRM_AUTH_HOSTNAME", socket.gethostname())
        auth = kerberos(username, password, realm=realm, address=address, hostname=hostname)
    elif method == "negotiate":
        auth = negotiate(username, password)
    else:
        raise RuntimeError(f"Unknown auth method from $WINRM_AUTH_METHOD: '{method}'")

    return WinRMClient(endpoint, auth=auth)


class TestAsyncWinRM(unittest.IsolatedAsyncioTestCase):
    client: WinRMClient

    def setUp(self):
        self.client = _get_client()

    async def testIdentify(self):
        response = await self.client.identify()
        self.assertEqual(response.protocol_version, "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd")
        self.assertIsNotNone(response.product_version)
        self.assertIsNotNone(response.product_vendor)

    async def testGetService(self):
        service = await self.client.get_service("LanmanWorkstation")
        self.assertEqual(service["Name"], "LanmanWorkstation")
        self.assertIn("svchost.exe", service["PathName"])

    async def testShell(self):
        shell = await self.client.shell()
        try:
            proc = await shell.create_subprocess_exec("cmd.exe", "/c", "ver")
            stdout, stderr = await proc.communicate()
            await proc.wait()
            decoded_stdout = stdout.decode() if stdout is not None else ""
            decoded_stderr = stderr.decode() if stderr is not None else ""
            self.assertIn("Microsoft Windows", decoded_stdout)
            self.assertEqual(decoded_stderr, "")
            self.assertIsNone(proc.returncode)
        finally:
            await shell.destroy()
