import asyncio
import os
import socket
import time
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


async def _read_until_contains(reader: asyncio.StreamReader, token: bytes, *, timeout: float = 8.0) -> bytes:
    buffer = bytearray()
    deadline = time.monotonic() + timeout
    while True:
        if token in buffer:
            return bytes(buffer)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"Timed out waiting for {token!r} in output")
        chunk = await asyncio.wait_for(reader.read(1024), timeout=remaining)
        print(chunk, end="", flush=True)
        if not chunk:
            raise AssertionError(f"EOF before {token!r} was seen in output")
        buffer.extend(chunk)


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
            proc = await shell.spawn("cmd.exe", "/c", "ver")
            stdout, stderr = await proc.communicate()
            await proc.wait()
            decoded_stdout = stdout.decode() if stdout is not None else ""
            decoded_stderr = stderr.decode() if stderr is not None else ""
            self.assertIn("Microsoft Windows", decoded_stdout)
            self.assertEqual(decoded_stderr, "")
            self.assertIsNone(proc.returncode)
        finally:
            await shell.destroy()

    async def testShellStdioStream(self):
        shell = await self.client.shell()
        try:
            proc = await shell.spawn("cmd.exe", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            assert proc.stdin is not None
            assert proc.stdout is not None

            await _read_until_contains(proc.stdout, b">")

            proc.stdin.write(b"echo hello\r\n")
            await proc.stdin.drain()
            # the first time is from our command getting echoed back, the second time is the actual output
            await _read_until_contains(proc.stdout, b"hello\r\nhello\r\n")

            proc.stdin.write(b"echo world\r\n")
            await proc.stdin.drain()
            await _read_until_contains(proc.stdout, b"world\r\nworld\r\n")

            proc.stdin.write(b"exit\r\n")
            await proc.stdin.drain()

            returncode = await proc.wait()
            self.assertEqual(returncode, 0)
        finally:
            await shell.destroy()

    async def testRegistry(self):
        key = self.client.registry.hklm.key(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        product = await key.get_string("ProductName")
        self.assertIsInstance(product, str)

        parent = self.client.registry.hklm.key(r"SOFTWARE\AsyncWinRMTest")
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
        service = await self.client.services.get("Spooler")
        self.assertIsInstance(service, Service)
        self.assertEqual(service.name, "Spooler")
        self.assertIsNotNone(service.display_name)

        services = await self.client.services.get_all()
        self.assertTrue(any(s.name == "Spooler" for s in services))

        initial_status = await service.get_status()
        if initial_status == ServiceState.Running:
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
