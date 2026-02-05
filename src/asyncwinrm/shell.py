import asyncio
import os
import stat
import time
from base64 import b64encode, b64decode
from collections.abc import Collection
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import PurePath
from subprocess import PIPE, STDOUT, DEVNULL
from typing import Optional, IO, Union, Iterable, TYPE_CHECKING, Callable, cast

from lxml import etree

from .exceptions import ProtocolError, TransportError, SOAPFaultError, WSManFaultError
from .protocol.action import (
    WindowsShellAction,
    WSTransferAction,
)
from .protocol.shell import WindowsShellSignal, StreamEvent, CommandState, CommandStateEvent
from .protocol.xml.element import RemoteShellElement
from .protocol.xml.namespace import Namespace

if TYPE_CHECKING:
    from .client.winrm import WinRMClient

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
        if len(data) == 0:
            return
        if self._writer is not None:
            self._writer.write(data)
            await self._writer.drain()
            return
        if self._fd is not None:

            def _write_all(fd: int, payload: bytes) -> None:
                view = memoryview(payload)
                offset = 0
                while offset < len(view):
                    try:
                        written = os.write(fd, view[offset:])
                    except BlockingIOError:
                        time.sleep(0.01)
                        continue
                    if written == 0:
                        raise BlockingIOError("write returned 0 bytes")
                    offset += written

            await asyncio.to_thread(_write_all, self._fd, data)
            return
        if self._file is not None:
            writer = cast(Callable[[bytes], int], self._file.write)
            await asyncio.to_thread(writer, data)
            await asyncio.to_thread(self._file.flush)

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            if hasattr(self._writer, "wait_closed"):
                await self._writer.wait_closed()
        if self._file is not None and not self._file.closed:
            await asyncio.to_thread(self._file.close)


class ShellWriter:
    """Async stdin writer for remote shell commands."""

    def __init__(
        self,
        shell: "Shell",
        command_id: str,
        done_event: asyncio.Event,
        chunk_size: Optional[int] = None,
    ):
        self._shell = shell
        self._command_id = command_id
        self._done_event = done_event
        self._chunk_size = chunk_size
        self._queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self._closed = False
        self._task = asyncio.create_task(self._send_loop())

    def write(self, data: bytes) -> None:
        if self._closed:
            raise RuntimeError("stdin is closed")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("stdin.write() expects bytes-like data")
        if self._done_event.is_set():
            return
        payload = bytes(data)
        if self._chunk_size is None or self._chunk_size <= 0:
            self._queue.put_nowait(payload)
            return
        for offset in range(0, len(payload), self._chunk_size):
            self._queue.put_nowait(payload[offset : offset + self._chunk_size])

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
                if self._done_event.is_set():
                    if data is None:
                        return
                    continue
                if data is None:
                    try:
                        await self._shell._send(self._command_id, b"", end=True, cancel_receive=True)
                    except TransportError:
                        return
                    return
                await self._shell._send(self._command_id, data, cancel_receive=True)
            finally:
                self._queue.task_done()


class Process:
    def __init__(
        self,
        shell: "Shell",
        command_id: str,
        stdin: Optional[ShellWriter],
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


@dataclass(slots=True)
class _CommandContext:
    command_id: str
    done_event: asyncio.Event = field(default_factory=asyncio.Event)
    stdin_task: Optional[asyncio.Task[None]] = None
    receive_cancel: asyncio.Event = field(default_factory=asyncio.Event)
    receive_idle: asyncio.Event = field(default_factory=asyncio.Event)


class _ReceiveCancelled(Exception):
    pass


class Shell:
    client: "WinRMClient"
    id: str
    destroyed = False

    def __init__(self, client: "WinRMClient", id: str) -> None:
        self.client = client
        self.id = id
        self._send_lock = asyncio.Lock()
        self._receive_lock = asyncio.Lock()
        self._command_contexts: dict[str, _CommandContext] = {}

    def _open_command_context(self, command_id: str) -> _CommandContext:
        ctx = _CommandContext(command_id=command_id)
        ctx.receive_idle.set()
        self._command_contexts[command_id] = ctx
        return ctx

    def _close_command_context(self, command_id: str) -> None:
        self._command_contexts.pop(command_id, None)

    @staticmethod
    def _suppress_task_cancelled(task: asyncio.Task[None]) -> None:
        try:
            task.exception()
        except asyncio.CancelledError:
            return

    @staticmethod
    def _is_operation_timeout_fault(exc: BaseException) -> bool:
        return isinstance(exc, WSManFaultError) and exc.wsman_code == "2150858793"

    async def destroy(self) -> None:
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")
        await self.client.request(
            WSTransferAction.Delete,
            resource_uri=f"{Namespace.WindowsRemoteShell}/cmd",
            selectors={"ShellId": self.id},
        )
        self.destroyed = True

    async def _command(
        self,
        command: str,
        arguments: Optional[Collection[str]] = None,
        *,
        console_mode_stdin: bool = True,
        skip_cmd_shell: bool = True,
    ) -> str:
        def _body(el_body: etree.Element) -> None:
            el_cl = etree.SubElement(
                el_body,
                RemoteShellElement.CommandLine,
                nsmap={"rsp": Namespace.WindowsRemoteShell},
            )
            etree.SubElement(el_cl, RemoteShellElement.Command).text = command
            if arguments is not None:
                for arg in arguments:
                    etree.SubElement(el_cl, RemoteShellElement.Arguments).text = arg

        response = await self.client.request(
            WindowsShellAction.Command,
            _body,
            resource_uri=f"{Namespace.WindowsRemoteShell}/cmd",
            selectors={"ShellId": self.id},
            data_element=RemoteShellElement.CommandResponse,
            options={
                "WINRS_CONSOLEMODE_STDIN": "TRUE" if console_mode_stdin else "FALSE",
                "WINRS_SKIP_CMD_SHELL": "TRUE" if skip_cmd_shell else "FALSE",
            },
        )
        command_id = response.data.findtext(RemoteShellElement.CommandID)
        if not command_id:
            raise ProtocolError("Command response missing CommandId")
        return command_id

    async def spawn(
        self,
        command: str,
        *args: str,
        stdin: Optional[ProcessSource] = PIPE,
        stdout: Optional[ProcessTarget] = PIPE,
        stderr: Optional[ProcessTarget] = PIPE,
        console_mode_stdin: bool = True,
        skip_cmd_shell: bool = True,
        stdin_chunk_size: Optional[int] = 65536,
    ) -> Process:
        if self.destroyed:
            raise RuntimeError("Shell has been destroyed")

        command_id = await self._command(
            command,
            args or None,
            console_mode_stdin=console_mode_stdin,
            skip_cmd_shell=skip_cmd_shell,
        )
        ctx = self._open_command_context(command_id)
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

        stdin_writer: Optional[ShellWriter] = None
        stdin_task: Optional[asyncio.Task[None]] = None
        if stdin == PIPE:
            stdin_writer = ShellWriter(self, command_id, ctx.done_event, stdin_chunk_size)
        elif stdin == DEVNULL:
            stdin_task = asyncio.create_task(self._send(command_id, b"", end=True, cancel_receive=False))
        elif stdin is not None:
            stdin_task = asyncio.create_task(self._feed_stdin(command_id, stdin, ctx.done_event, stdin_chunk_size))
            stdin_task.add_done_callback(self._suppress_task_cancelled)

        returncode_future: asyncio.Future[int] = asyncio.get_event_loop().create_future()
        receive_task = asyncio.create_task(
            self._receive_loop(
                command_id=command_id,
                stdout_reader=stdout_reader,
                stderr_reader=stderr_reader,
                stdout_sink=stdout_sink,
                stderr_sink=stderr_sink,
                returncode_future=returncode_future,
                context=ctx,
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
            ctx.stdin_task = stdin_task
        return process

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

        proc = await self.spawn(*cmd, stdin=stdin, stdout=stdout, stderr=stderr)
        out, err = await proc.communicate(input=input)
        returncode = await proc.wait()
        return CompletedProcess(args=cmd, returncode=returncode, stdout=out, stderr=err)

    async def _get_events(
        self,
        command_id: str,
        *,
        stdout: bool,
        stderr: bool,
        context: _CommandContext,
    ):
        def _body(el_body: etree.Element) -> None:
            el_receive = etree.SubElement(
                el_body, RemoteShellElement.Receive, nsmap={"rsp": Namespace.WindowsRemoteShell}
            )
            el_desired_stream = etree.SubElement(el_receive, RemoteShellElement.DesiredStream)
            el_desired_stream.set("CommandId", command_id)
            desired_stream = ""
            if stdout:
                desired_stream += " stdout"
            if stderr:
                desired_stream += " stderr"
            el_desired_stream.text = desired_stream.strip()

        async with self._receive_lock:
            context.receive_idle.clear()
            request_task = asyncio.create_task(
                self.client.request(
                    WindowsShellAction.Receive,
                    _body,
                    resource_uri=f"{Namespace.WindowsRemoteShell}/cmd",
                    selectors={"ShellId": self.id},
                    data_element=RemoteShellElement.ReceiveResponse,
                    timeout=1,
                )
            )
            cancel_task = asyncio.create_task(context.receive_cancel.wait())
            try:
                done, _ = await asyncio.wait(
                    {request_task, cancel_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if cancel_task in done and not request_task.done():
                    request_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await request_task
                    raise _ReceiveCancelled()
                response = await request_task
            finally:
                cancel_task.cancel()
                context.receive_idle.set()
        el_receive = response.data

        for el in el_receive:
            if el.tag == RemoteShellElement.Stream:
                stream_name: Optional[str] = el.get("Name")
                stream_command_id: Optional[str] = el.get("CommandId")
                if stream_name is None or stream_command_id is None:
                    raise ProtocolError("ReceiveResponse stream missing Name or CommandId")
                yield StreamEvent(
                    stream=stream_name,
                    command_id=stream_command_id,
                    content=b64decode(el.text) if el.text else b"",
                    finished=el.get("End") == "true",
                )
            elif el.tag == RemoteShellElement.CommandState:
                el_exit_code = el.find(RemoteShellElement.ExitCode)
                exit_code = None
                if el_exit_code is not None and el_exit_code.text is not None:
                    exit_code = int(el_exit_code.text)
                yield CommandStateEvent(
                    state=CommandState(el.get("State")),
                    exit_code=exit_code,
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
        context: _CommandContext,
    ) -> None:
        done = False
        stdout_finished = False
        stderr_finished = False
        returncode = 0
        done_seen = False

        try:
            while not done:
                try:
                    async for event in self._get_events(
                        command_id,
                        stdout=stdout_reader is not None or stdout_sink is not None,
                        stderr=stderr_reader is not None or stderr_sink is not None,
                        context=context,
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
                                done_seen = True
                                returncode = event.exit_code or 0
                                context.done_event.set()
                                if context.stdin_task is not None:
                                    context.stdin_task.cancel()
                                break
                except _ReceiveCancelled:
                    continue
                except SOAPFaultError as exc:
                    if self._is_operation_timeout_fault(exc):
                        continue
                    raise
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
            if done_seen:
                with suppress(Exception):
                    await self._signal(command_id, WindowsShellSignal.Terminate)
            if stdout_reader is not None:
                stdout_reader.feed_eof()
            if stderr_reader is not None:
                stderr_reader.feed_eof()

            if stdout_sink is not None:
                await stdout_sink.close()
            if stderr_sink is not None and stderr_sink is not stdout_sink:
                await stderr_sink.close()
            self._close_command_context(command_id)

    async def _send(
        self,
        command_id: str,
        data: bytes,
        *,
        end: bool = False,
        cancel_receive: bool = True,
    ) -> None:
        def _body(el_body: etree.Element) -> None:
            el_send = etree.SubElement(el_body, RemoteShellElement.Send, nsmap={"rsp": Namespace.WindowsRemoteShell})
            el_stream = etree.SubElement(el_send, RemoteShellElement.Stream)
            el_stream.set("CommandId", command_id)
            el_stream.set("Name", "stdin")
            if end:
                el_stream.set("End", "true")
            if data:
                el_stream.text = b64encode(data).decode("ascii")

        context = self._command_contexts.get(command_id)
        if cancel_receive and context is not None:
            context.receive_cancel.set()
            await context.receive_idle.wait()
            context.receive_cancel.clear()

        async with self._send_lock:
            await self.client.request(
                WindowsShellAction.Send,
                _body,
                resource_uri=f"{Namespace.WindowsRemoteShell}/cmd",
                selectors={"ShellId": self.id},
            )

    async def _signal(self, command_id: str, signal: WindowsShellSignal) -> None:
        def _body(el_body: etree.Element) -> None:
            el_signal = etree.SubElement(
                el_body, RemoteShellElement.Signal, nsmap={"rsp": Namespace.WindowsRemoteShell}
            )
            el_signal.set("CommandId", command_id)
            etree.SubElement(el_signal, RemoteShellElement.Code).text = signal

        await self.client.request(
            WindowsShellAction.Signal,
            _body,
            resource_uri=f"{Namespace.WindowsRemoteShell}/cmd",
            selectors={"ShellId": self.id},
        )

    async def _feed_stdin(
        self,
        command_id: str,
        source: ProcessSource,
        done_event: asyncio.Event,
        chunk_size: Optional[int],
    ) -> None:
        if source in (PIPE, STDOUT, DEVNULL):
            raise ValueError("Invalid stdin source")
        read_size = 65536 if not chunk_size or chunk_size <= 0 else chunk_size
        if isinstance(source, asyncio.StreamReader):
            while True:
                if done_event.is_set():
                    return
                chunk = await source.read(read_size)
                if not chunk:
                    break
                await self._send(command_id, chunk, cancel_receive=False)
            if not done_event.is_set():
                await self._send(command_id, b"", end=True, cancel_receive=False)
            return

        fd: Optional[int] = None
        if isinstance(source, int) and source not in (PIPE, STDOUT, DEVNULL):
            fd = source
            file_obj = os.fdopen(fd, "rb", closefd=False)
        elif isinstance(source, (str, PurePath)):
            file_obj = open(source, "rb")
        elif hasattr(source, "read"):
            file_obj = cast(IO[bytes], source)
            try:
                fd = file_obj.fileno()
            except Exception:
                fd = None
        else:
            raise TypeError("Unsupported stdin source type")

        try:
            use_reader = False
            if fd is not None:
                loop = asyncio.get_running_loop()
                use_reader = hasattr(loop, "add_reader")
                if use_reader:
                    try:
                        if stat.S_ISREG(os.fstat(fd).st_mode):
                            use_reader = False
                    except Exception:
                        use_reader = False

            if fd is not None and use_reader:
                try:
                    os.set_blocking(fd, False)
                except Exception:
                    pass

                queue: asyncio.Queue[Optional[object]] = asyncio.Queue(maxsize=1)
                reader_active = False

                def _enable_reader() -> None:
                    nonlocal reader_active
                    if not reader_active:
                        loop.add_reader(fd, _on_readable)
                        reader_active = True

                def _disable_reader() -> None:
                    nonlocal reader_active
                    if reader_active:
                        with suppress(Exception):
                            loop.remove_reader(fd)
                        reader_active = False

                def _on_readable() -> None:
                    if queue.full():
                        _disable_reader()
                        return
                    try:
                        chunk = os.read(fd, read_size)
                    except BlockingIOError:
                        return
                    except Exception as exc:
                        _disable_reader()
                        queue.put_nowait(exc)
                        return
                    if not chunk:
                        _disable_reader()
                        queue.put_nowait(None)
                        return
                    queue.put_nowait(chunk)
                    if queue.full():
                        _disable_reader()

                _enable_reader()
                try:
                    while True:
                        if done_event.is_set():
                            return
                        item = await queue.get()
                        if item is None:
                            break
                        if isinstance(item, BaseException):
                            raise item
                        await self._send(command_id, cast(bytes, item), cancel_receive=False)
                        if not reader_active:
                            _enable_reader()
                finally:
                    _disable_reader()
            elif fd is not None:
                while True:
                    if done_event.is_set():
                        return
                    try:
                        chunk = await asyncio.to_thread(os.read, fd, read_size)
                    except BlockingIOError:
                        await asyncio.sleep(0.01)
                        continue
                    if not chunk:
                        break
                    await self._send(command_id, chunk, cancel_receive=False)
            else:
                while True:
                    if done_event.is_set():
                        return
                    chunk = await asyncio.to_thread(file_obj.read, read_size)
                    if not chunk:
                        break
                    await self._send(command_id, chunk, cancel_receive=False)
        finally:
            with suppress(Exception):
                if hasattr(file_obj, "close"):
                    await asyncio.to_thread(file_obj.close)
        if not done_event.is_set():
            await self._send(command_id, b"", end=True, cancel_receive=False)
