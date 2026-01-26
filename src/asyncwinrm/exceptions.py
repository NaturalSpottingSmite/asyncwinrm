class WinRMError(Exception):
    """Base class for WinRM errors."""


class TransportError(WinRMError):
    """HTTP transport or connectivity error."""


class ProtocolError(WinRMError):
    """Malformed or unexpected WS-Management response."""


class SOAPFaultError(WinRMError):
    """SOAP fault response returned by the server."""

    def __init__(self, reason: str, code: str | None = None) -> None:
        self.reason = reason
        self.code = code
        super().__init__(reason if code is None else f"{reason} ({code})")
