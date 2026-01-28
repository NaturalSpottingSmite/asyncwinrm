from dataclasses import dataclass
from typing import Optional, Self

import httpx
from lxml import etree

from ..exceptions import TransportError, SoapFaultError
from ..protocol.xml.element import SoapElement


@dataclass
class SoapEnvelope:
    """SOAP envelope"""

    root: etree.Element

    @classmethod
    def new(cls, nsmap: dict[str, str]) -> Self:
        """Creates a new, empty envelope."""
        envelope = cls(etree.Element(SoapElement.Envelope, nsmap=nsmap))
        # ensure headers and body exist
        envelope.header
        envelope.body
        return envelope

    @property
    def header(self) -> etree.Element:
        el = self.root.find(SoapElement.Header)
        return el if el is not None else etree.SubElement(self.root, SoapElement.Header)

    @property
    def body(self) -> etree.Element:
        el = self.root.find(SoapElement.Body)
        return el if el is not None else etree.SubElement(self.root, SoapElement.Body)

    def __bytes__(self) -> bytes:
        return etree.tostring(self.root, xml_declaration=True, encoding="utf-8")


@dataclass
class SoapResponse(SoapEnvelope):
    """A SOAP envelope that was received as a response"""

    http_response: httpx.Response

    @property
    def fault(self) -> Optional[tuple[Optional[str], Optional[str]]]:
        el_fault = self.body.find(SoapElement.Fault)
        if el_fault is not None:
            code = None
            reason = None

            el_code = el_fault.find(SoapElement.Code)
            if el_code is not None:
                el_value = el_code.find(SoapElement.Value)
                if el_value is not None:
                    code = el_value.text

            el_reason = el_fault.find(SoapElement.Reason)
            if el_reason is not None:
                el_text = el_reason.find(SoapElement.Text)
                if el_text is not None:
                    reason = el_text.text

            return code, reason
        return None

    def raise_for_status(self) -> Self:
        """Raises an exception if the response indicates a failure."""

        fault = self.fault
        if fault is not None:
            raise SoapFaultError(*fault)

        try:
            self.http_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TransportError(e)

        return self


@dataclass(frozen=True, slots=True)
class SoapClient:
    """SOAP client"""

    http: httpx.AsyncClient

    async def close(self):
        """Closes the client and any currently open connections."""
        await self.http.aclose()

    async def request(self, envelope: SoapEnvelope) -> SoapResponse:
        """Executes a SOAP request and returns a response."""
        request = self.http.build_request("POST", "", content=bytes(envelope))
        response = await self.http.send(request)
        try:
            root = etree.fromstring(response.content)
            return SoapResponse(root, http_response=response)
        except Exception:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise TransportError(e)
            raise
        finally:
            await response.aclose()


__all__ = ["SoapEnvelope", "SoapResponse", "SoapClient"]
