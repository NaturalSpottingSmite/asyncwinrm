from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from .xml.namespace import Namespace


class WindowsShellSignal(StrEnum):
    CtrlC = f"{Namespace.WindowsRemoteShell}/signal/ctrl_c"
    Terminate = f"{Namespace.WindowsRemoteShell}/signal/Terminate"


@dataclass(frozen=True, slots=True)
class StreamEvent:
    stream: str
    command_id: str
    content: Optional[bytes]
    finished: bool


class CommandState(StrEnum):
    Running = f"{Namespace.WindowsRemoteShell}/CommandState/Running"
    Done = f"{Namespace.WindowsRemoteShell}/CommandState/Done"


@dataclass(frozen=True, slots=True)
class CommandStateEvent:
    state: Optional[CommandState]
    exit_code: Optional[int]


type ReceiveEvent = StreamEvent | CommandStateEvent


__all__ = [
    "WindowsShellSignal",
    "StreamEvent",
    "CommandState",
    "CommandStateEvent",
    "ReceiveEvent",
]
