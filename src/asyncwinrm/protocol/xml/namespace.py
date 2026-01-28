from enum import StrEnum

from ..uri import uri


class Namespace(StrEnum):
    Xml = "http://www.w3.org/XML/1998/namespace"
    Xs = "http://www.w3.org/2001/XMLSchema"
    Xsi = "http://www.w3.org/2001/XMLSchema-instance"

    Soap = "http://www.w3.org/2003/05/soap-envelope"
    WsAddressing = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
    WsTransfer = "http://schemas.xmlsoap.org/ws/2004/09/transfer"
    WsEventing = "http://schemas.xmlsoap.org/ws/2004/08/eventing"
    WsEnumeration = "http://schemas.xmlsoap.org/ws/2004/09/enumeration"
    WsManagement = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"

    # Not included in the global namespace map
    WsManagementIdentity = "http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd"
    # WsMan = "https://schemas.microsoft.com/wbem/wsman/1/wsman.xsd"
    WindowsRemoteShell = uri("windows", "shell")
    Cim = "http://schemas.dmtf.org/wbem/wscim/1/common"

    @classmethod
    def nsmap(cls) -> dict[str, str]:
        # Use same abbreviations as WinRM responses.
        return {
            "xml": cls.Xml,  # must always use the reserved xml: namespace
            "s": cls.Soap,
            "a": cls.WsAddressing,
            "x": cls.WsTransfer,
            "e": cls.WsEventing,
            "n": cls.WsEnumeration,
            "w": cls.WsManagement,
        }


__all__ = ["Namespace"]
