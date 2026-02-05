import uuid
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Optional, AsyncGenerator

import httpx
from lxml import etree

from .soap import SOAPClient, SOAPEnvelope, SOAPResponse
from ..exceptions import ProtocolError
from ..protocol.action import WSTransferAction, WSEnumerationAction
from ..protocol.xml.element import (
    WSAddressingElement,
    WSManagementElement,
    WSManagementIdentityElement,
    WSEnumerationElement,
)
from ..protocol.xml.attribute import XMLAttribute, SOAPAttribute
from ..protocol.xml.namespace import Namespace
import logging

from ..utils import DurationLike, sec_to_duration

type Builder = Callable[[etree.Element], None]


@dataclass
class WSManagementEnvelope(SOAPEnvelope):
    """WS-Management envelope"""

    @property
    def to(self) -> Optional[str]:
        el_to = self.header.find(WSAddressingElement.To)
        return el_to.text if el_to is not None else None

    @to.setter
    def to(self, new_value: Optional[str]) -> None:
        el_to = self.header.find(WSAddressingElement.To)
        if el_to is None and new_value is not None:
            el_to = etree.SubElement(self.header, WSAddressingElement.To)

        if el_to is not None and new_value is not None:
            el_to.text = new_value
        elif el_to is not None:
            self.header.remove(el_to)

    @property
    def reply_to(self) -> Optional[str]:
        el_reply_to = self.header.find(WSAddressingElement.ReplyTo)
        if el_reply_to is not None:
            el_address = el_reply_to.find(WSAddressingElement.Address)
            if el_address is not None:
                return el_address.text

        return None

    @reply_to.setter
    def reply_to(self, new_value: Optional[str]) -> None:
        el_reply_to = self.header.find(WSAddressingElement.ReplyTo)
        if el_reply_to is None and new_value is not None:
            el_reply_to = etree.SubElement(self.header, WSAddressingElement.ReplyTo)

        if el_reply_to is not None:
            el_address = el_reply_to.find(WSAddressingElement.Address)
            if el_address is None and new_value is not None:
                el_address = etree.SubElement(el_reply_to, WSAddressingElement.Address)
                el_address.set(SOAPAttribute.MustUnderstand, "true")

            if el_address is not None and new_value is not None:
                el_address.text = new_value
            elif el_address is not None or el_reply_to is not None:
                if el_address is not None:
                    self.header.remove(el_address)
                self.header.remove(el_reply_to)

    @property
    def action(self) -> Optional[str]:
        el_action = self.header.find(WSAddressingElement.Action)
        return el_action.text if el_action is not None else None

    @action.setter
    def action(self, new_value: Optional[str]) -> None:
        el_action = self.header.find(WSAddressingElement.Action)
        if el_action is None and new_value is not None:
            el_action = etree.SubElement(self.header, WSAddressingElement.Action)
            el_action.set(SOAPAttribute.MustUnderstand, "true")

        if el_action is not None and new_value is not None:
            el_action.text = new_value
        elif el_action is not None:
            self.header.remove(el_action)

    @property
    def message_id(self) -> Optional[str]:
        el_message_id = self.header.find(WSAddressingElement.MessageID)
        return el_message_id.text if el_message_id is not None else None

    @message_id.setter
    def message_id(self, new_value: Optional[str]):
        el_message_id = self.header.find(WSAddressingElement.MessageID)
        if el_message_id is None and new_value is not None:
            el_message_id = etree.SubElement(self.header, WSAddressingElement.MessageID)

        if el_message_id is not None and new_value is not None:
            el_message_id.text = new_value
        elif el_message_id is not None:
            self.header.remove(el_message_id)

    @property
    def resource_uri(self) -> Optional[str]:
        el_resource_uri = self.header.find(WSManagementElement.ResourceURI)
        return el_resource_uri.text if el_resource_uri is not None else None

    @resource_uri.setter
    def resource_uri(self, new_value: Optional[str]) -> None:
        el_resource_uri = self.header.find(WSManagementElement.ResourceURI)
        if el_resource_uri is None and new_value is not None:
            el_resource_uri = etree.SubElement(
                self.header,
                WSManagementElement.ResourceURI,
            )
            el_resource_uri.set(SOAPAttribute.MustUnderstand, "true")

        if el_resource_uri is not None and new_value is not None:
            el_resource_uri.text = new_value
        elif el_resource_uri is not None:
            self.header.remove(el_resource_uri)

    @property
    def selectors(self) -> Optional[MappingProxyType]:
        el_selector_set = self.header.find(WSManagementElement.SelectorSet)
        if el_selector_set is not None:
            selectors = {}
            for el_selector in el_selector_set.findall(WSManagementElement.Selector):
                selectors[el_selector.get("Name")] = el_selector.text
            return MappingProxyType(selectors)
        return None

    @selectors.setter
    def selectors(self, new_value: Optional[dict[str, str]]):
        el_selector_set = self.header.find(WSManagementElement.SelectorSet)
        if el_selector_set is None and new_value is not None:
            el_selector_set = etree.SubElement(
                self.header,
                WSManagementElement.SelectorSet,
            )
        elif el_selector_set is not None and new_value is not None:
            el_selector_set.clear()

        if el_selector_set is not None and new_value is not None:
            for name, value in new_value.items():
                el_selector = etree.SubElement(
                    el_selector_set,
                    WSManagementElement.Selector,
                )
                el_selector.set("Name", name)
                el_selector.text = value
        elif el_selector_set is not None:
            self.header.remove(el_selector_set)

    @property
    def options(self) -> Optional[MappingProxyType]:
        el_option_set = self.header.find(WSManagementElement.OptionSet)
        if el_option_set is not None:
            options = {}
            for el_option in el_option_set.findall(WSManagementElement.Option):
                options[el_option.get("Name")] = el_option.text
            return MappingProxyType(options)
        return None

    @options.setter
    def options(self, new_value: Optional[dict[str, str]]):
        el_option_set = self.header.find(WSManagementElement.OptionSet)
        if el_option_set is None and new_value is not None:
            el_option_set = etree.SubElement(self.header, WSManagementElement.OptionSet)
            el_option_set.set(SOAPAttribute.MustUnderstand, "true")
        elif el_option_set is not None and new_value is not None:
            el_option_set.clear()

        if el_option_set is not None and new_value is not None:
            for name, value in new_value.items():
                el_option = etree.SubElement(el_option_set, WSManagementElement.Option)
                el_option.set("Name", name)
                el_option.text = value
        elif el_option_set is not None:
            self.header.remove(el_option_set)

    @property
    def locale(self) -> Optional[str]:
        el_locale = self.header.find(WSManagementElement.Locale)
        return el_locale.get(XMLAttribute.Lang) if el_locale is not None else None

    @locale.setter
    def locale(self, new_value: Optional[str]) -> None:
        el_locale = self.header.find(WSManagementElement.Locale)
        if el_locale is None and new_value is not None:
            el_locale = etree.SubElement(self.header, WSManagementElement.Locale)
            el_locale.set(SOAPAttribute.MustUnderstand, "false")

        if el_locale is not None and new_value is not None:
            el_locale.set(XMLAttribute.Lang, new_value)
        elif el_locale is not None:
            self.header.remove(el_locale)

    @property
    def data_locale(self) -> Optional[str]:
        el_data_locale = self.header.find(WSManagementElement.DataLocale)
        return el_data_locale.get(XMLAttribute.Lang) if el_data_locale is not None else None

    @data_locale.setter
    def data_locale(self, new_value: Optional[str]) -> None:
        el_data_locale = self.header.find(WSManagementElement.DataLocale)
        if el_data_locale is None and new_value is not None:
            el_data_locale = etree.SubElement(self.header, WSManagementElement.DataLocale)
            el_data_locale.set(SOAPAttribute.MustUnderstand, "false")

        if el_data_locale is not None and new_value is not None:
            el_data_locale.set(XMLAttribute.Lang, new_value)
        elif el_data_locale is not None:
            self.header.remove(el_data_locale)

    @property
    def timeout(self) -> Optional[str]:
        el_timeout = self.header.find(WSManagementElement.OperationTimeout)
        return el_timeout.text if el_timeout is not None else None

    @timeout.setter
    def timeout(self, new_value: Optional[str]) -> None:
        el_timeout = self.header.find(WSManagementElement.OperationTimeout)
        if el_timeout is None and new_value is not None:
            el_timeout = etree.SubElement(
                self.header,
                WSManagementElement.OperationTimeout,
            )

        if el_timeout is not None and new_value is not None:
            el_timeout.text = new_value
        elif el_timeout is not None:
            self.header.remove(el_timeout)

    @property
    def max_size(self) -> Optional[int]:
        el_max_size = self.header.find(WSManagementElement.MaxEnvelopeSize)
        if el_max_size is not None:
            value = el_max_size.text
            if value is not None:
                return int(value)

        return None

    @max_size.setter
    def max_size(self, new_value: Optional[int]) -> None:
        el_max_size = self.header.find(WSManagementElement.MaxEnvelopeSize)
        if el_max_size is None and new_value is not None:
            el_max_size = etree.SubElement(
                self.header,
                WSManagementElement.MaxEnvelopeSize,
            )
            el_max_size.set(SOAPAttribute.MustUnderstand, "true")

        if el_max_size is not None and new_value is not None:
            el_max_size.text = str(new_value)
        elif el_max_size is not None:
            self.header.remove(el_max_size)


@dataclass
class WSManagementResponse(WSManagementEnvelope, SOAPResponse):
    """A WS-Management envelope that was received as a response"""

    data_element: Optional[etree.QName]

    @property
    def data(self) -> etree.Element:
        body = super().body
        if self.data_element is None:
            return body[0]
        el_body = body.find(self.data_element)
        if el_body is None:
            raise ProtocolError(f"Missing body element: {self.data_element.localname} ({self.data_element.namespace})")
        return el_body


@dataclass
class WSManagementIdentifyResponse(WSManagementResponse):
    """Response from WS-Management Identify action"""

    @property
    def protocol_version(self) -> Optional[str]:
        """Returns the remote server's protocol version as a URI."""
        el_protocol_version = self.data.find(WSManagementIdentityElement.ProtocolVersion)
        return el_protocol_version.text if el_protocol_version is not None else None

    @property
    def product_vendor(self) -> Optional[str]:
        """Returns the remote server software product's vendor."""
        el_product_vendor = self.data.find(WSManagementIdentityElement.ProductVendor)
        return el_product_vendor.text if el_product_vendor is not None else None

    @property
    def product_version(self) -> Optional[str]:
        """Returns the remote server software product's version."""
        el_product_version = self.data.find(WSManagementIdentityElement.ProductVersion)
        return el_product_version.text if el_product_version is not None else None

    @property
    def security_profiles(self) -> Optional[list[str]]:
        """Returns the remote server's supported security profiles as a list of URIs."""
        el_security_profiles = self.data.find(WSManagementIdentityElement.SecurityProfiles)
        if el_security_profiles is not None:
            security_profiles = []
            for el_security_profile in el_security_profiles.findall(WSManagementIdentityElement.SecurityProfileName):
                security_profiles.append(el_security_profile.text)
            return security_profiles
        return None


class WSManagementClient:
    """WS-Management client"""

    __slots__ = ("_logger", "_soap", "endpoint", "locale", "timeout", "max_envelope_size")

    _logger: logging.Logger
    _soap: SOAPClient
    endpoint: httpx.URL
    locale: Optional[str]
    timeout: Optional[DurationLike]
    max_envelope_size: Optional[int]

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint: httpx.URL,
        *,
        locale: Optional[str] = None,
        timeout: Optional[DurationLike] = None,
        max_envelope_size: Optional[int] = None,
    ):
        self._logger = logging.getLogger(__name__)
        self._soap = SOAPClient(client)
        self.endpoint = endpoint
        self.locale = locale
        self.timeout = timeout
        self.max_envelope_size = max_envelope_size

    async def close(self):
        """Closes the client and any currently open connections."""
        await self._soap.close()

    async def identify(self) -> WSManagementIdentifyResponse:
        """Tests the connection and returns protocol information."""
        envelope = WSManagementEnvelope.new({"s": Namespace.SOAP, "wsmid": Namespace.WSManagementIdentity})
        etree.SubElement(envelope.body, WSManagementIdentityElement.Identify)

        response = await self.run_request(envelope, WSManagementIdentityElement.IdentifyResponse)
        return WSManagementIdentifyResponse(
            response.root,
            http_response=response.http_response,
            data_element=WSManagementIdentityElement.IdentifyResponse,
        )

    # === Requests ===

    def build_request(
        self,
        action: str,
        body: Optional[etree.Element | Builder] = None,
        *,
        resource_uri: Optional[str] = None,
        message_id: Optional[str] = None,
        selectors: Optional[dict[str, str]] = None,
        options: Optional[dict[str, str]] = None,
        locale: Optional[str] = None,
        timeout: Optional[DurationLike] = None,
        max_size: Optional[int] = None,
    ) -> WSManagementEnvelope:
        """
        Constructs a request.

        :param action: The action to execute on the resource.
        :param body: An optional body element or builder function to use as the request body.
        :param resource_uri: The resource to execute the action on. Defaults to None.
        :param message_id: A unique identifier for this message. Defaults to a randomly generated UUIDv4.
        :param selectors: The selectors to apply to locate the resource if it is not a singleton. Defaults to None.
        :param options: Additional options to specify for the operation. Defaults to None.
        :param locale: Locale to use for human-readable messages. Defaults to the client's locale.
        :param timeout: Timeout for the operation. Defaults to the client's timeout.
        :param max_size: Maximum envelope size the server will return. Defaults to the client's maximum envelope size.
        :return: A WSManagementEnvelope that contains the request body and can be used to execute the request.
        """
        envelope = WSManagementEnvelope.new(Namespace.nsmap())
        envelope.to = str(self.endpoint)
        envelope.reply_to = f"{Namespace.WSAddressing}/role/anonymous"
        envelope.action = action
        envelope.message_id = message_id if message_id is not None else f"urn:uuid:{uuid.uuid4()}"
        envelope.resource_uri = resource_uri
        envelope.selectors = selectors
        envelope.options = options

        if locale is None:
            locale = self.locale

        envelope.locale = locale
        envelope.data_locale = locale

        if timeout is None:
            timeout = self.timeout

        if timeout is not None:
            envelope.timeout = sec_to_duration(timeout)

        envelope.max_size = max_size or self.max_envelope_size

        if isinstance(body, Callable):
            body(envelope.body)
        elif etree.iselement(body):
            envelope.body.append(body)

        return envelope

    async def run_request(
        self,
        envelope: WSManagementEnvelope,
        data_element: Optional[etree.QName],
    ) -> WSManagementResponse:
        """
        Executes a WS-Management request from an envelope.

        :param envelope: The envelope to send as the request body.
        :param data_element: The element in the body to find and use as the response's "data" property. If None, will
                             use the body's first child.
        :return: A response for the request.
        """
        response = await self._soap.request(envelope)
        response.raise_for_status()
        return WSManagementResponse(response.root, http_response=response.http_response, data_element=data_element)

    async def request(
        self,
        action: str,
        body: Optional[etree.Element | Builder] = None,
        *,
        data_element: Optional[etree.QName] = None,
        resource_uri: Optional[str] = None,
        message_id: Optional[str] = None,
        selectors: Optional[dict[str, str]] = None,
        options: Optional[dict[str, str]] = None,
        locale: Optional[str] = None,
        timeout: Optional[DurationLike] = None,
        max_size: Optional[int] = None,
    ) -> WSManagementResponse:
        """
        Constructs and executes a request.

        :param action: The action to execute on the resource.
        :param body: An optional body element or builder function to use as the request body.
        :param data_element: The element in the body to find and use as the response's "data" property. If None, will
                             use the body's first child.
        :param resource_uri: The resource to execute the action on.
        :param message_id: A unique identifier for this message. Defaults to a randomly generated UUIDv4.
        :param selectors: The selectors to apply to locate the resource if it is not a singleton. Defaults to None.
        :param options: Additional options to specify for the operation. Defaults to None.
        :param locale: Locale to use for human-readable messages. Defaults to the client's locale.
        :param timeout: Timeout for the operation. Defaults to the client's timeout.
        :param max_size: Maximum envelope size the server will return. Defaults to the client's maximum envelope size.
        :return: A response for the request, with the "data" property set to the first occurrence of "data_element".
        """
        envelope = self.build_request(
            action,
            body,
            resource_uri=resource_uri,
            message_id=message_id,
            selectors=selectors,
            options=options,
            locale=locale,
            timeout=timeout,
            max_size=max_size,
        )

        self._logger.info("request action=%s resource_uri=%s", action, resource_uri)
        return await self.run_request(envelope, data_element)

    async def get(
        self,
        resource_uri: str,
        *,
        data_element: Optional[etree.QName] = None,
        selectors: Optional[dict[str, str]] = None,
        options: Optional[dict[str, str]] = None,
    ) -> WSManagementResponse:
        """
        Gets a resource.

        :param resource_uri: The resource to get.
        :param data_element: The element in the body to find and use as the response's "data" property. If None, will
                             use the body's first child.
        :param selectors: The selectors to apply to locate the resource if it is not a singleton. Defaults to None.
        :param options: Additional options to specify for the operation. Defaults to None.
        :return: A response containing the resource, with the "data" property set to the first occurrence of
                 "data_element".
        """
        return await self.request(
            WSTransferAction.Get,
            data_element=data_element,
            resource_uri=resource_uri,
            selectors=selectors,
            options=options,
        )

    async def enumerate(
        self,
        resource_uri: str,
        *,
        selectors: Optional[dict[str, str]] = None,
        options: Optional[dict[str, str]] = None,
        max_elements: int = 100,
    ) -> AsyncGenerator[etree.Element]:
        """
        Enumerates a resource.

        :param resource_uri: The resource to get.
                             use the body's first child.
        :param selectors: The selectors to apply to locate the resource if it is not a singleton. Defaults to None.
        :param options: Additional options to specify for the operation. Defaults to None.
        :param max_elements: The maximum number of elements to return per pull. Defaults to 100. Note that enumerator
                             pulls are completely abstracted away, so this is more of an internal option. Additionally,
                             since each pull response is buffered in memory (*not* using an XML pull parser), this value
                             should be kept relatively small to prevent using up large amounts of memory.
        :return: A generator yielding all elements in the enumeration.
        """
        enum_body = etree.Element(WSEnumerationElement.Enumerate)
        etree.SubElement(enum_body, WSManagementElement.OptimizeOperation)
        etree.SubElement(enum_body, WSEnumerationElement.MaxElements).text = str(max_elements)

        context: Optional[etree.Element] = None

        resp = await self.request(
            WSEnumerationAction.Enumerate,
            enum_body,
            data_element=WSEnumerationElement.EnumerateResponse,
            resource_uri=resource_uri,
            selectors=selectors,
            options=options,
        )

        body = etree.Element(WSEnumerationElement.Pull)
        etree.SubElement(body, WSEnumerationElement.MaxElements).text = str(max_elements)

        finished = False
        next_context: Optional[etree.Element]
        try:
            while not finished:
                next_context = context
                for el in resp.data:
                    if el.tag == WSEnumerationElement.EnumerationContext:
                        next_context = el
                    elif el.tag == WSEnumerationElement.Items:
                        for item in el:
                            yield item
                    elif el.tag == WSEnumerationElement.EndOfSequence:
                        finished = True
                if context is not None:
                    body.remove(context)
                if next_context is None:
                    raise ProtocolError("EnumerationContext missing from response")
                context = next_context
                body.append(context)
                if not finished:
                    resp = await self.request(
                        WSEnumerationAction.Pull,
                        body,
                        data_element=WSEnumerationElement.PullResponse,
                        resource_uri=resource_uri,
                        selectors=selectors,
                        options=options,
                    )
        finally:
            if not finished and context is not None:
                await self.request(
                    WSEnumerationAction.Release,
                    lambda b: etree.SubElement(b, WSEnumerationElement.Release).append(context),
                    resource_uri=resource_uri,
                    selectors=selectors,
                    options=options,
                )


__all__ = ["WSManagementEnvelope", "WSManagementResponse", "WSManagementIdentifyResponse", "WSManagementClient"]
