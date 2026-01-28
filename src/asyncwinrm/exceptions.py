from typing import Optional


class WinRMError(Exception):
    """Base class for WinRM errors."""


class TransportError(WinRMError):
    """HTTP transport or connectivity error."""


class ProtocolError(WinRMError):
    """Malformed or unexpected WS-Management response."""

    # TODO: put XML here or make a new error


class SoapFaultError(WinRMError):
    """SOAP fault response returned by the server."""

    code: Optional[str]
    reason: Optional[str]

    def __init__(self, code: Optional[str], reason: Optional[str]) -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"{reason or 'Unknown/generic SOAP fault'} ({code or 'no code'})")
