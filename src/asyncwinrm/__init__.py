import logging
from enum import StrEnum
from rich import print

from .schema import Element, WindowsShellSignal, uri
from .soap import WinRmClient
from .auth import kerberos, ntlm, basic

class AuthStrategy(StrEnum):
    GssApi = "gssapi"


async def main() -> None:
    logging.basicConfig(
        format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG
    )

    conn = WinRmClient(
        "127.0.0.1",
        auth=basic("Administrator", "password"),
    )

    # res = await conn.get_service("sshd")
    # print(res)

    shell = await conn.create_shell()
    print(shell)
    command = await conn.command_shell(shell["ShellId"], "powershell.exe")
    print(command)
    try:
        async for thing in conn.receive_shell(shell["ShellId"], command["CommandId"]):
            print(thing)
        await conn.send_shell(
            shell["ShellId"], command["CommandId"], b"$PSVersionTable.PSVersion\r\n"
        )
        async for thing in conn.receive_shell(shell["ShellId"], command["CommandId"]):
            print(thing)
        await conn.send_shell(shell["ShellId"], command["CommandId"], b"exit\r\n")
        async for thing in conn.receive_shell(shell["ShellId"], command["CommandId"]):
            print(thing)
        await conn.signal_shell(
            shell["ShellId"], command["CommandId"], WindowsShellSignal.Terminate
        )
    finally:
        await conn.delete_shell(shell["ShellId"])
