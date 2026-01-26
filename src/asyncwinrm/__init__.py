import logging

from .connection import Connection
from .auth.basic import basic
from .exceptions import WinRMError, TransportError, ProtocolError, SOAPFaultError


async def main() -> None:
    # logging.basicConfig(
    #     format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    #     datefmt="%Y-%m-%d %H:%M:%S",
    #     level=logging.DEBUG,
    # )

    conn = Connection(
        "http://172.16.17.137:5985",
        auth=basic("Administrator", "password"),
    )

    shell = await conn.shell()
    try:
        proc = await shell.create_subprocess_exec("powershell.exe", "-NoLogo")
        stdout, stderr = await proc.communicate(b"$PSVersionTable.PSVersion\r\nexit\r\n")
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
    finally:
        await shell.destroy()


__all__ = [
    "Connection",
]
