from dataclasses import dataclass
from typing import Optional, Self

import httpx
from lxml import etree

from ..exceptions import TransportError, SOAPFaultError, WSManFaultError
from ..protocol.xml.element import SOAPElement, WSManFaultElement


@dataclass
class SOAPEnvelope:
    """SOAP envelope"""

    root: etree.Element

    @classmethod
    def new(cls, nsmap: dict[str, str]) -> Self:
        """Creates a new, empty envelope."""
        envelope = cls(etree.Element(SOAPElement.Envelope, nsmap=nsmap))
        # ensure headers and body exist
        envelope.header
        envelope.body
        return envelope

    @property
    def header(self) -> etree.Element:
        el = self.root.find(SOAPElement.Header)
        return el if el is not None else etree.SubElement(self.root, SOAPElement.Header)

    @property
    def body(self) -> etree.Element:
        el = self.root.find(SOAPElement.Body)
        return el if el is not None else etree.SubElement(self.root, SOAPElement.Body)

    def __bytes__(self) -> bytes:
        return etree.tostring(self.root, xml_declaration=True, encoding="utf-8")


@dataclass
class SOAPResponse(SOAPEnvelope):
    """A SOAP envelope that was received as a response"""

    http_response: httpx.Response

    @property
    def fault(self) -> Optional[tuple[Optional[str], Optional[str], Optional[str]]]:
        # print(etree.tostring(self.body, pretty_print=True, encoding="unicode"))
        el_fault = self.body.find(SOAPElement.Fault)
        if el_fault is not None:
            code = None
            reason = None
            wsman_code = None

            el_code = el_fault.find(SOAPElement.Code)
            if el_code is not None:
                el_value = el_code.find(SOAPElement.Value)
                if el_value is not None:
                    code = el_value.text

            el_reason = el_fault.find(SOAPElement.Reason)
            if el_reason is not None:
                el_text = el_reason.find(SOAPElement.Text)
                if el_text is not None:
                    reason = el_text.text

            el_detail = el_fault.find(SOAPElement.Detail)
            if el_detail is not None:
                el_wsman_fault = el_detail.find(WSManFaultElement.WSManFault)
                if el_wsman_fault is not None:
                    wsman_code = el_wsman_fault.get("Code")

            return code, reason, wsman_code
        return None

    def raise_for_status(self) -> Self:
        """Raises an exception if the response indicates a failure."""

        fault = self.fault
        if fault is not None:
            soap_code, reason, wsman_code = fault
            if wsman_code is not None:
                raise WSManFaultError(soap_code, reason, wsman_code)
            raise SOAPFaultError(soap_code, reason)

        try:
            self.http_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TransportError(e)

        return self


@dataclass(frozen=True, slots=True)
class SOAPClient:
    """SOAP client"""

    http: httpx.AsyncClient

    async def close(self):
        """Closes the client and any currently open connections."""
        await self.http.aclose()

    async def request(self, envelope: SOAPEnvelope) -> SOAPResponse:
        """Executes a SOAP request and returns a response."""
        request = self.http.build_request("POST", "", content=bytes(envelope))
        response = await self.http.send(request)
        try:
            root = etree.fromstring(response.content)
            return SOAPResponse(root, http_response=response)
        except Exception:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise TransportError(e)
            raise
        finally:
            await response.aclose()


__all__ = ["SOAPEnvelope", "SOAPResponse", "SOAPClient"]
