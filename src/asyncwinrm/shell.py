import asyncio
import os
from base64 import b64encode, b64decode
from collections.abc import Collection
from contextlib import suppress
from dataclasses import dataclass
from pathlib import PurePath
from subprocess import PIPE, STDOUT, DEVNULL
from typing import Optional, IO, Union, Iterable, TYPE_CHECKING

from lxml import etree

from .exceptions import ProtocolError
from .protocol.soap import (
    StreamEvent,
    CommandStateEvent,
    CommandState,
    WindowsShellSignal,
    Namespace,
    WindowsShellAction,
    Element,
    WsTransferAction,
)

if TYPE_CHECKING:
    from .connection import Connection

ProcessSource = Union[int, str, PurePath, asyncio.StreamReader, IO[bytes]]
ProcessTarget = Union[int, str, PurePath, asyncio.StreamWriter, IO[bytes]]


class _OutputSink:
    def __init__(self, target: Optional[ProcessTarget]):
        self._target = target
        self._writer: Optional[asyncio.StreamWriter] = None
        self._file: Optional[IO[bytes]] = None
        self._fd: Optional[int] = None

        if isinstance(target, asyncio.StreamWriter):
            self._writer = target
        elif isinstance(target, int) and target not in (PIPE, STDOUT, DEVNULL):
            self._fd = target
        elif isinstance(target, (str, PurePath)):
            self._file = open(target, "ab")
        elif hasattr(target, "write"):
            self._file = target  # type: ignore[assignment]

    async def write(self, data: bytes) -> None:
        if not data:
            return
        if self._writer is not None:
            self._writer.write(data)
            await self._writer.drain()
            return
        if self._fd is not None:
            await asyncio.to_thread(os.write, self._fd, data)
            return
        if self._file is not None:
            await asyncio.to_thread(self._file.write, data)
            await asyncio.to_thread(self._file.flush)

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            if hasattr(self._writer, "wait_closed"):
                await self._writer.wait_closed()
        if self._file is not None and not self._file.closed:
            await asyncio.to_thread(self._file.close)


class _StdinWriter:
    def __init__(self, shell: "Shell", command_id: str):
        self._shell = shell
        self._command_id = command_id
        self._queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self._closed = False
        self._task = asyncio.create_task(self._send_loop())

    def write(self, data: bytes) -> None:
        if self._closed:
            raise RuntimeError("stdin is closed")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("stdin.write() expects bytes-like data")
        self._queue.put_nowait(bytes(data))

    def writelines(self, lines: Iterable[bytes]) -> None:
        for line in lines:
            self.write(line)

    async def drain(self) -> None:
        await self._queue.join()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._queue.put_nowait(None)

    def is_closing(self) -> bool:
        return self._closed

    async def wait_closed(self) -> None:
        await self._task

    async def _send_loop(self) -> None:
        while True:
            data = await self._queue.get()
            try:
                if data is None:
                    await self._shell._send(self._command_id, b"", end=True)
                    return
                await self._shell._send(self._command_id, data)
            finally:
                self._queue.task_done()


class Process:
    def __init__(
        self,
        shell: "Shell",
        command_id: str,
        stdin: Optional[_StdinWriter],
        stdout: Optional[asyncio.StreamReader],
        stderr: Optional[asyncio.StreamReader],
        receive_task: asyncio.Task[None],
        returncode_future: asyncio.Future[int],
    ):
        self.shell = shell
        self.command_id = command_id
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self._receive_task = receive_task
        self._stdin_task: Optional[asyncio.Task[None]] = None
        self.returncode: Optional[int] = None
        self._returncode_future = returncode_future
        self._returncode_future.add_done_callback(self._sync_returncode)
        self.pid: Optional[int] = None

    def _sync_returncode(self, fut: asyncio.Future[int]) -> None:
        if fut.cancelled():
            return
        if fut.exception() is None:
            self.returncode = fut.result()

    async def wait(self) -> int:
        if self._returncode_future.done():
            return self._returncode_future.result()
        return await self._returncode_future

    async def communicate(self, input: Optional[bytes] = None) -> tuple[Optional[bytes], Optional[bytes]]:
        if input is not None:
            if self.stdin is None:
                raise ValueError("Process stdin is not a pipe")
            self.stdin.write(input)
            await self.stdin.drain()
            self.stdin.close()

        stdout_data: Optional[bytes] = None
        stderr_data: Optional[bytes] = None

        if self.stdout is not None:
            stdout_data = await self.stdout.read()
        if self.stderr is not None and self.stderr is not self.stdout:
            stderr_data = await self.stderr.read()

        await self.wait()
        return stdout_data, stderr_data

    async def send_signal(self, sig: WindowsShellSignal) -> None:
        await self.shell._signal(self.command_id, sig)

    async def terminate(self) -> None:
        await self.send_signal(WindowsShellSignal.Terminate)

    async def kill(self) -> None:
        await self.send_signal(WindowsShellSignal.Terminate)


@dataclass
class CompletedProcess:
    args: tuple[str, ...]
    returncode: int
    stdout: Optional[bytes]
    stderr: Optional[bytes]


class Shell:
    connection: "Connection"
    id: str
    destroyed = False

    def __init__(self, connection: "Connection", id: str) -> None:
        self.connection = connection
        self.id = id

    async def destroy(self) -> None:
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")
        await self.connection.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WsTransferAction.Delete,
            selectors={"ShellId": self.id},
        )
        self.destroyed = True

    async def _command(self, command: str, arguments: Optional[Collection[str]] = None) -> str:
        def _body(el_body: etree.Element) -> None:
            el_cl = etree.SubElement(
                el_body,
                Element.CommandLine,
                nsmap={"rsp": Namespace.WindowsRemoteShell},
            )
            etree.SubElement(el_cl, Element.Command).text = command
            if arguments is not None:
                for arg in arguments:
                    etree.SubElement(el_cl, Element.Arguments).text = arg

        body = await self.connection.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Command,
            selectors={"ShellId": self.id},
            body=_body,
        )
        el_command = body.find(Element.CommandResponse)
        if el_command is None:
            raise ProtocolError("Command response missing CommandResponse")
        command_id = el_command.findtext(Element.CommandId)
        if not command_id:
            raise ProtocolError("Command response missing CommandId")
        return command_id

    async def create_subprocess_exec(
        self,
        program: str,
        *args: str,
        stdin: Optional[ProcessSource] = PIPE,
        stdout: Optional[ProcessTarget] = PIPE,
        stderr: Optional[ProcessTarget] = PIPE,
    ) -> Process:
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")

        command_id = await self._command(program, args)
        stdout_reader: Optional[asyncio.StreamReader] = None
        stderr_reader: Optional[asyncio.StreamReader] = None
        stdout_sink = None
        stderr_sink = None

        if stdout == STDOUT:
            raise ValueError("stdout cannot be STDOUT")
        if stdout == PIPE:
            stdout_reader = asyncio.StreamReader()
        elif stdout == DEVNULL:
            stdout_sink = _OutputSink(None)
        elif stdout is not None:
            stdout_sink = _OutputSink(stdout)

        if stderr == PIPE:
            stderr_reader = asyncio.StreamReader()
        elif stderr == STDOUT and stdout_reader is not None:
            stderr_reader = stdout_reader
        elif stderr == STDOUT and stdout_sink is not None:
            stderr_sink = stdout_sink
        elif stderr == DEVNULL:
            stderr_sink = _OutputSink(None)
        elif stderr is not None:
            stderr_sink = _OutputSink(stderr)

        stdin_writer: Optional[_StdinWriter] = None
        stdin_task: Optional[asyncio.Task[None]] = None
        if stdin == PIPE:
            stdin_writer = _StdinWriter(self, command_id)
        elif stdin == DEVNULL:
            stdin_task = asyncio.create_task(self._send(command_id, b"", end=True))
        elif stdin is not None:
            stdin_task = asyncio.create_task(self._feed_stdin(command_id, stdin))
            stdin_task.add_done_callback(lambda t: t.exception())

        returncode_future: asyncio.Future[int] = asyncio.get_event_loop().create_future()
        receive_task = asyncio.create_task(
            self._receive_loop(
                command_id=command_id,
                stdout_reader=stdout_reader,
                stderr_reader=stderr_reader,
                stdout_sink=stdout_sink,
                stderr_sink=stderr_sink,
                returncode_future=returncode_future,
            ),
        )

        process = Process(
            shell=self,
            command_id=command_id,
            stdin=stdin_writer,
            stdout=stdout_reader,
            stderr=stderr_reader,
            receive_task=receive_task,
            returncode_future=returncode_future,
        )
        if stdin_task is not None:
            process._stdin_task = stdin_task
        return process

    async def create_subprocess_shell(
        self,
        command: str,
        stdin: Optional[ProcessSource] = None,
        stdout: Optional[ProcessTarget] = None,
        stderr: Optional[ProcessTarget] = None,
    ) -> Process:
        return await self.create_subprocess_exec("cmd.exe", "/c", command, stdin=stdin, stdout=stdout, stderr=stderr)

    async def run(
        self,
        *cmd: str,
        input: Optional[bytes] = None,
        stdout: Optional[ProcessTarget] = None,
        stderr: Optional[ProcessTarget] = None,
        capture_output: bool = False,
    ) -> CompletedProcess:
        if capture_output:
            stdout = PIPE
            stderr = PIPE
        if input is not None:
            stdin: Optional[ProcessSource] = PIPE
        else:
            stdin = None

        proc = await self.create_subprocess_exec(*cmd, stdin=stdin, stdout=stdout, stderr=stderr)
        out, err = await proc.communicate(input=input)
        returncode = await proc.wait()
        return CompletedProcess(args=cmd, returncode=returncode, stdout=out, stderr=err)

    async def _get_events(self, command_id: str, *, stdout: bool, stderr: bool):
        def _body(el_body: etree.Element) -> None:
            el_receive = etree.SubElement(el_body, Element.Receive, nsmap={"rsp": Namespace.WindowsRemoteShell})
            el_desired_stream = etree.SubElement(el_receive, Element.DesiredStream)
            el_desired_stream.set("CommandId", command_id)
            desired_stream = ""
            if stdout:
                desired_stream += " stdout"
            if stderr:
                desired_stream += " stderr"
            el_desired_stream.text = desired_stream.strip()

        async for body in self.connection.request_stream(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Receive,
            selectors={"ShellId": self.id},
            body=_body,
        ):
            el_receive = body.find(Element.ReceiveResponse)
            if el_receive is None:
                continue

            for el in el_receive:
                if el.tag == Element.Stream:
                    yield StreamEvent(
                        stream=el.get("Name"),
                        command_id=el.get("CommandId"),
                        content=b64decode(el.text) if el.text else b"",
                        finished=el.get("End") == "true",
                    )
                elif el.tag == Element.CommandState:
                    el_exit_code = el.find(Element.ExitCode)
                    yield CommandStateEvent(
                        state=el.get("State"),
                        exit_code=(int(el_exit_code.text) if el_exit_code is not None else None),
                    )
                else:
                    raise ProtocolError(f"Unknown ReceiveResponse element: {el.tag}")

    async def _receive_loop(
        self,
        command_id: str,
        stdout_reader: Optional[asyncio.StreamReader],
        stderr_reader: Optional[asyncio.StreamReader],
        stdout_sink: Optional[_OutputSink],
        stderr_sink: Optional[_OutputSink],
        returncode_future: asyncio.Future[int],
    ) -> None:
        done = False
        stdout_finished = False
        stderr_finished = False
        returncode = 0

        try:
            while not done:
                async for event in self._get_events(
                    command_id,
                    stdout=stdout_reader is not None or stdout_sink is not None,
                    stderr=stderr_reader is not None or stderr_sink is not None,
                ):
                    if isinstance(event, StreamEvent):
                        if event.stream == "stdout":
                            if stdout_reader is not None:
                                stdout_reader.feed_data(event.content or b"")
                            if stdout_sink is not None:
                                await stdout_sink.write(event.content or b"")
                            if event.finished:
                                stdout_finished = True
                                if stdout_reader is not None:
                                    stdout_reader.feed_eof()
                        elif event.stream == "stderr":
                            if stderr_reader is not None:
                                stderr_reader.feed_data(event.content or b"")
                            if stderr_sink is not None:
                                await stderr_sink.write(event.content or b"")
                            if event.finished:
                                stderr_finished = True
                                if stderr_reader is not None:
                                    stderr_reader.feed_eof()
                    elif isinstance(event, CommandStateEvent):
                        if event.state == CommandState.Done:
                            done = True
                            returncode = event.exit_code or 0
                            break

                if stdout_finished and stderr_finished:
                    done = True
        except Exception as exc:
            if not returncode_future.done():
                returncode_future.set_exception(exc)
            raise
        else:
            if not returncode_future.done():
                returncode_future.set_result(returncode)
        finally:
            if stdout_reader is not None:
                stdout_reader.feed_eof()
            if stderr_reader is not None:
                stderr_reader.feed_eof()

            if stdout_sink is not None:
                await stdout_sink.close()
            if stderr_sink is not None and stderr_sink is not stdout_sink:
                await stderr_sink.close()

    async def _send(self, command_id: str, data: bytes, *, end: bool = False) -> None:
        def _body(el_body: etree.Element) -> None:
            el_send = etree.SubElement(el_body, Element.Send, nsmap={"rsp": Namespace.WindowsRemoteShell})
            el_stream = etree.SubElement(el_send, Element.Stream)
            el_stream.set("CommandId", command_id)
            el_stream.set("Name", "stdin")
            if end:
                el_stream.set("End", "true")
            if data:
                el_stream.text = b64encode(data).decode("ascii")

        await self.connection.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Send,
            selectors={"ShellId": self.id},
            body=_body,
        )

    async def _signal(self, command_id: str, signal: WindowsShellSignal) -> None:
        def _body(el_body: etree.Element) -> None:
            el_signal = etree.SubElement(el_body, Element.Signal, nsmap={"rsp": Namespace.WindowsRemoteShell})
            el_signal.set("CommandId", command_id)
            etree.SubElement(el_signal, Element.Code).text = signal

        await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Signal,
            selectors={"ShellId": self.id},
            body=_body,
        )

    async def _feed_stdin(self, command_id: str, source: ProcessSource) -> None:
        if source in (PIPE, STDOUT, DEVNULL):
            raise ValueError("Invalid stdin source")
        if isinstance(source, asyncio.StreamReader):
            while True:
                chunk = await source.read(32768)
                if not chunk:
                    break
                await self._send(command_id, chunk)
            await self._send(command_id, b"", end=True)
            return

        if isinstance(source, int) and source not in (PIPE, STDOUT, DEVNULL):
            file_obj: IO[bytes] = os.fdopen(source, "rb", closefd=False)
        elif isinstance(source, (str, PurePath)):
            file_obj = open(source, "rb")
        elif hasattr(source, "read"):
            file_obj = source
        else:
            raise TypeError("Unsupported stdin source type")

        try:
            while True:
                chunk = await asyncio.to_thread(file_obj.read, 32768)
                if not chunk:
                    break
                await self._send(command_id, chunk)
        finally:
            with suppress(Exception):
                if hasattr(file_obj, "close"):
                    await asyncio.to_thread(file_obj.close)
        await self._send(command_id, b"", end=True)
