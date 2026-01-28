from enum import StrEnum

from .xml.namespace import Namespace


class WsTransferAction(StrEnum):
    Get = f"{Namespace.WsTransfer}/Get"
    Put = f"{Namespace.WsTransfer}/Put"
    Create = f"{Namespace.WsTransfer}/Create"
    Delete = f"{Namespace.WsTransfer}/Delete"


class WsEnumerationAction(StrEnum):
    Enumerate = f"{Namespace.WsEnumeration}/Enumerate"
    Pull = f"{Namespace.WsEnumeration}/Pull"
    Renew = f"{Namespace.WsEnumeration}/Renew"
    GetStatus = f"{Namespace.WsEnumeration}/GetStatus"
    Release = f"{Namespace.WsEnumeration}/Release"


class WsEventingAction(StrEnum):
    Subscribe = f"{Namespace.WsEventing}/Subscribe"
    Renew = f"{Namespace.WsEventing}/Renew"
    GetStatus = f"{Namespace.WsEventing}/GetStatus"
    Unsubscribe = f"{Namespace.WsEventing}/Unsubscribe"


class WindowsShellAction(StrEnum):
    Command = f"{Namespace.WindowsRemoteShell}/Command"
    Send = f"{Namespace.WindowsRemoteShell}/Send"
    Receive = f"{Namespace.WindowsRemoteShell}/Receive"
    Signal = f"{Namespace.WindowsRemoteShell}/Signal"


type Action = WsTransferAction | WsEnumerationAction | WsEventingAction | WindowsShellAction

__all__ = [
    "WsTransferAction",
    "WsEnumerationAction",
    "WsEventingAction",
    "WindowsShellAction",
    "Action",
]
