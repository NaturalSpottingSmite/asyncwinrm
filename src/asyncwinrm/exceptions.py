from typing import Optional


class WinRMError(Exception):
    """Base class for WinRM errors."""


class TransportError(WinRMError):
    """HTTP transport or connectivity error."""


class ProtocolError(WinRMError):
    """Malformed or unexpected WS-Management response."""

    # TODO: put XML here or make a new error


class SOAPFaultError(WinRMError):
    """SOAP fault response returned by the server."""

    code: Optional[str]
    reason: Optional[str]

    def __init__(self, code: Optional[str], reason: Optional[str]) -> None:
        self.code = code
        self.reason = reason
        details = code or "no code"
        super().__init__(f"{reason or 'Unknown/generic SOAP fault'} ({details})")


class WSManFaultError(SOAPFaultError):
    """SOAP fault response that includes a WS-Management fault code."""

    wsman_code: Optional[str]

    def __init__(self, code: Optional[str], reason: Optional[str], wsman_code: Optional[str]) -> None:
        super().__init__(code, reason)
        self.wsman_code = wsman_code
        details = wsman_code or "no code"
        if wsman_code:
            self.args = (f"{self.reason or 'Unknown/generic WS-Management fault'} ({details})",)


class EncryptionError(WinRMError):
    """WinRM message encryption error."""
