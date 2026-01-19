import asyncio
import socket
from pathlib import PurePath
from typing import Union, IO

from .. import WindowsShellSignal
from ..connection import Connection

ProcessSource = Union[int, str, socket.socket, PurePath, asyncio.StreamReader, IO[bytes]]
ProcessTarget = Union[int, str, socket.socket, PurePath, asyncio.StreamWriter, IO[bytes]]


class ShellProcessReader:
    process: "ShellProcess"


class ShellProcessWriter:
    process: "ShellProcess"


class ShellProcess:
    shell: "Shell"
    id: str

    def __init__(self, shell: "Shell", id: str):
        self.shell = shell
        self.id = id

    async def signal(self, sig: WindowsShellSignal) -> None:
        """Send a signal to the remote process."""
        await self.shell.signal_process(self.id, sig)

    async def terminate(self) -> None:
        """Terminate the remote process."""
        await self.signal(WindowsShellSignal.Terminate)


class Shell:
    connection: Connection
    id: str

    destroyed = False

    def __init__(self, connection: Connection, id: str) -> None:
        self.connection = connection
        self.id = id

    async def destroy(self) -> None:
        """
        Destroys the shell, cleaning up associated resources on the remote host.

        The shell cannot be used after this method has been called.
        """
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")

        await self.connection.delete_shell(self.id)
        self.destroyed = True

    async def run_command(self, *command: str) -> ShellProcess:
        """
        Run a command in the shell.

        :param command: The command to run. The first element is used as the program name, the rest of the elements are
                        passed as arguments.
        :returns: A ShellProcess object that can be used to interact with the running process.
        """
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")

        data = await self.connection.command_shell(self.id, command[0], command[1:])
        return ShellProcess(shell=self, id=data["CommandId"])

    async def signal_process(self, process_id: str, sig: WindowsShellSignal) -> None:
        """Send a signal to a remote process."""
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")

        await self.connection.signal_shell(self.id, process_id, sig)
