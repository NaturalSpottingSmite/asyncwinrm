from enum import StrEnum

from ..uri import uri


class Namespace(StrEnum):
    Xml = "http://www.w3.org/XML/1998/namespace"
    Xs = "http://www.w3.org/2001/XMLSchema"
    Xsi = "http://www.w3.org/2001/XMLSchema-instance"

    SOAP = "http://www.w3.org/2003/05/soap-envelope"
    WSAddressing = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
    WSTransfer = "http://schemas.xmlsoap.org/ws/2004/09/transfer"
    WSEventing = "http://schemas.xmlsoap.org/ws/2004/08/eventing"
    WSEnumeration = "http://schemas.xmlsoap.org/ws/2004/09/enumeration"
    WSManagement = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
    WSManFault = "http://schemas.microsoft.com/wbem/wsman/1/wsmanfault"

    # Not included in the global namespace map
    WSManagementIdentity = "http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd"
    # WSMan = "https://schemas.microsoft.com/wbem/wsman/1/wsman.xsd"
    WindowsRemoteShell = uri("windows", "shell")
    CIM = "http://schemas.dmtf.org/wbem/wscim/1/common"

    @classmethod
    def nsmap(cls) -> dict[str, str]:
        # Use same abbreviations as WinRM responses.
        return {
            "xml": cls.Xml,  # must always use the reserved xml: namespace
            "s": cls.SOAP,
            "a": cls.WSAddressing,
            "x": cls.WSTransfer,
            "e": cls.WSEventing,
            "n": cls.WSEnumeration,
            "w": cls.WSManagement,
        }


__all__ = ["Namespace"]
