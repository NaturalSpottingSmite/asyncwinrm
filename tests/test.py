import asyncio
import os
import socket
import unittest
from contextlib import suppress

from asyncwinrm.auth.spnego import negotiate, kerberos
from asyncwinrm.client.winrm import WinRMClient
from asyncwinrm.wmi.services import Service, ServiceState


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

    async def asyncSetUp(self) -> None:
        loop = asyncio.get_running_loop()
        loop.set_debug(False)

    async def asyncTearDown(self):
        await self.client.close()

    async def testIdentify(self):
        response = await self.client.identify()
        self.assertEqual(response.protocol_version, "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd")
        self.assertIsNotNone(response.product_version)
        self.assertIsNotNone(response.product_vendor)

    async def testReauth(self):
        response = await self.client.identify()
        self.assertEqual(response.protocol_version, "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd")
        await asyncio.sleep(15)
        response = await self.client.identify()
        self.assertEqual(response.protocol_version, "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd")

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

    async def testRegistry(self):
        key = self.client.registry.hklm.key(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        product = await key.get_string("ProductName")
        self.assertIsInstance(product, str)

        parent = self.client.registry.hkcu.key(r"Software\AsyncWinRMTest")
        await parent.create()
        child = None
        expected_value_names = {
            "TestValue",
            "TestValue64",
            "TestString",
            "TestExpand",
            "TestMulti",
            "TestBinary",
        }

        try:
            child = parent.key("Child")
            await child.create()
            await parent.set_dword("TestValue", 42)
            await parent.set_qword("TestValue64", 2**40)
            await parent.set_string("TestString", "hello")
            await parent.set_expand_string("TestExpand", r"%SystemRoot%\System32")
            await parent.set_multi_string("TestMulti", ["one", "two"])
            await parent.set_binary("TestBinary", b"\x00\x01\xfe")

            self.assertEqual(await parent.get_dword("TestValue"), 42)
            self.assertEqual(await parent.get_qword("TestValue64"), 2**40)
            self.assertEqual(await parent.get_string("TestString"), "hello")
            # self.assertIsInstance(await parent.get_expand_string("TestExpand"), str)
            self.assertEqual(await parent.get_expand_string("TestExpand"), r"C:\Windows\System32")
            self.assertEqual(await parent.get_multi_string("TestMulti"), ["one", "two"])
            self.assertEqual(await parent.get_binary("TestBinary"), b"\x00\x01\xfe")

            values = await parent.list_values()
            value_names = {value.name for value in values}
            self.assertEqual(value_names, expected_value_names)

            async with parent as values_view:
                self.assertEqual(values_view["TestValue"], 42)
                self.assertEqual(values_view["TestString"], "hello")
                with self.assertRaises(TypeError):
                    values_view["TestValue"] = 7  # ty: ignore[invalid-assignment]

            subkeys = await parent.list_subkeys()
            self.assertIn("Child", subkeys)

            for name in expected_value_names:
                await parent.delete_value(name)
        finally:
            if child is not None:
                with suppress(Exception):
                    await child.delete()
            with suppress(Exception):
                await parent.delete()

    async def testServices(self):
        # Basic get / get_all
        service = await self.client.services.get("Spooler")
        self.assertIsInstance(service, Service)
        self.assertEqual(service.name, "Spooler")
        self.assertIsNotNone(service.display_name)

        services = await self.client.services.get_all()
        self.assertTrue(any(s.name == "Spooler" for s in services))

        # Start/stop and verify status changes (Spooler is non-essential)
        initial_status = await service.get_status()
        self.assertIn(initial_status, (ServiceState.Running, ServiceState.Stopped, ServiceState.Paused))

        await service.stop()
        for _ in range(25):  # up to 5s
            if await service.get_status() == ServiceState.Stopped:
                break
            await asyncio.sleep(0.2)
        self.assertEqual(await service.get_status(), ServiceState.Stopped)

        await service.start()
        for _ in range(25):  # up to 5s
            if await service.get_status() == ServiceState.Running:
                break
            await asyncio.sleep(0.2)
        self.assertEqual(await service.get_status(), ServiceState.Running)
