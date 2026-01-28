from .client.winrm import WinRmClient
from .client.wsman import WsManagementClient
from .auth.basic import basic
from .exceptions import WinRMError, TransportError, ProtocolError, SoapFaultError
from .protocol.uri import cim


async def main() -> None:
    # logging.basicConfig(
    #     format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    #     datefmt="%Y-%m-%d %H:%M:%S",
    #     level=logging.DEBUG,
    # )

    conn = WinRmClient(
        "http://172.16.17.137:5985",
        auth=basic("Administrator", "password"),
    )

    id = await conn.identify()
    print(id)
    print(f"Protocol version: {id.protocol_version}")
    print(f"Product vendor: {id.product_vendor}")
    print(f"Product version: {id.product_version}")
    print(f"Security profiles: {id.security_profiles}")

    print(await conn.get_service("sshd"))

    # async for resp in conn.enumerate(cim("Win32_Service")):
    #     print("got service")

    shell = await conn.shell()
    try:
        # proc = await shell.create_subprocess_exec("powershell.exe", "-NoLogo")
        # stdout, stderr = await proc.communicate(b"$PSVersionTable.PSVersion\r\nexit\r\n")
        proc = await shell.create_subprocess_exec("cmd.exe")
        stdout, stderr = await proc.communicate(b"dir\r\nexit\r\n")
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
    finally:
        await shell.destroy()


__all__ = [
    "WinRmClient",
    "WsManagementClient",
    "basic",
    "WinRMError",
    "TransportError",
    "ProtocolError",
    "SoapFaultError",
    "cim",
]
