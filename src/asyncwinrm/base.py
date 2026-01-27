from typing import Optional, AsyncGenerator

import httpx
from lxml import etree

from .exceptions import SOAPFaultError, ProtocolError, TransportError
from .protocol.soap import Element, Namespace, WsTransferAction, Action, build_wsman_request, Builder


class BaseConnection:
    """Low-level WinRM protocol client (SOAP, headers, streaming parser)."""

    endpoint: httpx.URL
    http: httpx.AsyncClient
    locale: Optional[str]
    timeout: Optional[int]
    max_envelope_size: Optional[int]

    def __init__(
        self,
        endpoint: httpx.URL,
        auth: Optional[httpx.Auth] = None,
        verify: bool = True,
        locale: Optional[str] = None,
        timeout: Optional[int] = None,
        max_envelope_size: Optional[int] = None,
    ):
        self.locale = locale
        self.timeout = timeout
        self.max_envelope_size = max_envelope_size
        self.endpoint = endpoint
        self.http = httpx.AsyncClient(
            base_url=endpoint,
            auth=auth,
            verify=verify,
            headers={
                "Content-Type": "application/soap+xml; charset=UTF-8",
            },
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def __aenter__(self) -> "BaseConnection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def do_request(self, envelope: etree.Element) -> AsyncGenerator[etree.Element, None]:
        content = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")

        req = self.http.build_request("POST", "", content=content)
        try:
            resp = await self.http.send(req, stream=True)
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc

        try:
            async for response in self._parse_response_stream(resp):
                yield response
        finally:
            await resp.aclose()


    async def request_stream(
        self,
        *,
        resource: str,
        action: Action = WsTransferAction.Get,
        selectors: Optional[dict[str, str]] = None,
        options: Optional[dict[str, str]] = None,
        body: Optional[Builder] = None,
        timeout: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> AsyncGenerator[etree.Element, None]:
        envelope = build_wsman_request(
            endpoint=str(self.endpoint),
            resource=resource,
            action=action,
            selectors=selectors,
            options=options,
            body=body,
            locale=self.locale,
            timeout=timeout or self.timeout,
            max_size=max_size or self.max_envelope_size,
        )

        async for response in self.do_request(envelope):
            yield response

    async def request(
        self,
        *,
        resource: str,
        action: Action = WsTransferAction.Get,
        selectors: Optional[dict[str, str]] = None,
        options: Optional[dict[str, str]] = None,
        body: Optional[Builder] = None,
        timeout: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> etree.Element:
        async for response in self.request_stream(
            resource=resource,
            action=action,
            selectors=selectors,
            options=options,
            body=body,
            timeout=timeout,
            max_size=max_size,
        ):
            return response
        raise ProtocolError("No SOAP envelope received")

    async def _parse_response_stream(self, resp: httpx.Response) -> AsyncGenerator[etree.Element, None]:
        parser = etree.XMLPullParser(events=("end",), tag=Element.Envelope)
        seen_envelope = False

        async for chunk in resp.aiter_bytes():
            parser.feed(chunk)
            for _, envelope in parser.read_events():
                seen_envelope = True
                body = envelope.find(Element.Body)
                if body is None:
                    raise ProtocolError("SOAP envelope missing Body")

                fault = body.find(Element.Fault)
                if fault is not None:
                    raise self._parse_fault(fault)

                if not resp.is_success:
                    raise TransportError(f"HTTP {resp.status_code}: {resp.reason_phrase}")

                yield body
                envelope.clear()

        parser.close()
        if not seen_envelope and not resp.is_success:
            raise TransportError(f"HTTP {resp.status_code}: {resp.reason_phrase}")

    @staticmethod
    def _parse_fault(fault: etree.Element) -> SOAPFaultError:
        reason = None
        code = None

        el_reason = fault.find(Element.Reason)
        if el_reason is not None:
            el_text = el_reason.find(Element.Text)
            if el_text is not None:
                reason = el_text.text

        el_code = fault.find(etree.QName(Namespace.Soap, "Code"))
        if el_code is not None:
            el_value = el_code.find(etree.QName(Namespace.Soap, "Value"))
            if el_value is not None:
                code = el_value.text

        return SOAPFaultError(reason=reason or "Unknown SOAP fault", code=code)
