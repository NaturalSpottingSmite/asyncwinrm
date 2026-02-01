from enum import StrEnum

from .xml.namespace import Namespace


class WSTransferAction(StrEnum):
    Get = f"{Namespace.WSTransfer}/Get"
    Put = f"{Namespace.WSTransfer}/Put"
    Create = f"{Namespace.WSTransfer}/Create"
    Delete = f"{Namespace.WSTransfer}/Delete"


class WSEnumerationAction(StrEnum):
    Enumerate = f"{Namespace.WSEnumeration}/Enumerate"
    Pull = f"{Namespace.WSEnumeration}/Pull"
    Renew = f"{Namespace.WSEnumeration}/Renew"
    GetStatus = f"{Namespace.WSEnumeration}/GetStatus"
    Release = f"{Namespace.WSEnumeration}/Release"


class WSEventingAction(StrEnum):
    Subscribe = f"{Namespace.WSEventing}/Subscribe"
    Renew = f"{Namespace.WSEventing}/Renew"
    GetStatus = f"{Namespace.WSEventing}/GetStatus"
    Unsubscribe = f"{Namespace.WSEventing}/Unsubscribe"


class WindowsShellAction(StrEnum):
    Command = f"{Namespace.WindowsRemoteShell}/Command"
    Send = f"{Namespace.WindowsRemoteShell}/Send"
    Receive = f"{Namespace.WindowsRemoteShell}/Receive"
    Signal = f"{Namespace.WindowsRemoteShell}/Signal"


__all__ = [
    "WSTransferAction",
    "WSEnumerationAction",
    "WSEventingAction",
    "WindowsShellAction",
]
