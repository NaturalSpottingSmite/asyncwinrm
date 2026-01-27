import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional, Callable

from lxml import etree

WINDOWS_WSMAN_PREFIX = "http://schemas.microsoft.com/wbem/wsman/1"


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
    WindowsRemoteShell = "http://schemas.microsoft.com/wbem/wsman/1/windows/shell"

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


WS_MANAGEMENT_PREFIX = Namespace.WsManagement.removesuffix(".xsd")


class Element:
    # SOAP Envelope
    Envelope = etree.QName(Namespace.Soap, "Envelope")
    Header = etree.QName(Namespace.Soap, "Header")
    Body = etree.QName(Namespace.Soap, "Body")
    Fault = etree.QName(Namespace.Soap, "Fault")
    Reason = etree.QName(Namespace.Soap, "Reason")
    Text = etree.QName(Namespace.Soap, "Text")

    # WS-Addressing
    To = etree.QName(Namespace.WsAddressing, "To")
    Action = etree.QName(Namespace.WsAddressing, "Action")
    Address = etree.QName(Namespace.WsAddressing, "Address")
    ReplyTo = etree.QName(Namespace.WsAddressing, "ReplyTo")
    MessageId = etree.QName(Namespace.WsAddressing, "MessageID")
    ReferenceParameters = etree.QName(Namespace.WsAddressing, "ReferenceParameters")

    # WS-Transfer
    ResourceCreated = etree.QName(Namespace.WsTransfer, "ResourceCreated")

    # WS-Management
    ResourceUri = etree.QName(Namespace.WsManagement, "ResourceURI")
    MaxEnvelopeSize = etree.QName(Namespace.WsManagement, "MaxEnvelopeSize")
    Locale = etree.QName(Namespace.WsManagement, "Locale")
    SelectorSet = etree.QName(Namespace.WsManagement, "SelectorSet")
    Selector = etree.QName(Namespace.WsManagement, "Selector")
    OptionSet = etree.QName(Namespace.WsManagement, "OptionSet")
    Option = etree.QName(Namespace.WsManagement, "Option")
    OperationTimeout = etree.QName(Namespace.WsManagement, "OperationTimeout")

    # WS-Management Identity
    Identify = etree.QName(Namespace.WsManagementIdentity, "Identify")
    IdentifyResponse = etree.QName(Namespace.WsManagementIdentity, "IdentifyResponse")

    # Windows Remote Shell
    Shell = etree.QName(Namespace.WindowsRemoteShell, "Shell")
    ShellId = etree.QName(Namespace.WindowsRemoteShell, "ShellId")
    Environment = etree.QName(Namespace.WindowsRemoteShell, "Environment")
    Variable = etree.QName(Namespace.WindowsRemoteShell, "Variable")
    WorkingDirectory = etree.QName(Namespace.WindowsRemoteShell, "WorkingDirectory")
    Lifetime = etree.QName(Namespace.WindowsRemoteShell, "Lifetime")
    InputStreams = etree.QName(Namespace.WindowsRemoteShell, "InputStreams")
    OutputStreams = etree.QName(Namespace.WindowsRemoteShell, "OutputStreams")
    CommandLine = etree.QName(Namespace.WindowsRemoteShell, "CommandLine")
    Command = etree.QName(Namespace.WindowsRemoteShell, "Command")
    Arguments = etree.QName(Namespace.WindowsRemoteShell, "Arguments")
    CommandResponse = etree.QName(Namespace.WindowsRemoteShell, "CommandResponse")
    CommandId = etree.QName(Namespace.WindowsRemoteShell, "CommandId")
    Receive = etree.QName(Namespace.WindowsRemoteShell, "Receive")
    DesiredStream = etree.QName(Namespace.WindowsRemoteShell, "DesiredStream")
    Signal = etree.QName(Namespace.WindowsRemoteShell, "Signal")
    Code = etree.QName(Namespace.WindowsRemoteShell, "Code")
    ReceiveResponse = etree.QName(Namespace.WindowsRemoteShell, "ReceiveResponse")
    Stream = etree.QName(Namespace.WindowsRemoteShell, "Stream")
    CommandState = etree.QName(Namespace.WindowsRemoteShell, "CommandState")
    ExitCode = etree.QName(Namespace.WindowsRemoteShell, "ExitCode")
    Send = etree.QName(Namespace.WindowsRemoteShell, "Send")


class Attribute:
    MustUnderstand = etree.QName(Namespace.Soap, "mustUnderstand")
    Lang = etree.QName(Namespace.Xml, "lang")
    Nil = etree.QName(Namespace.Xsi, "nil")


class WsTransferAction(StrEnum):
    Get = f"{Namespace.WsTransfer}/Get"
    Put = f"{Namespace.WsTransfer}/Put"
    Create = f"{Namespace.WsTransfer}/Create"
    Delete = f"{Namespace.WsTransfer}/Delete"


class WsEnumerationAction(StrEnum):
    Enumerate = f"{Namespace.WsEnumeration}/Enumerate"
    Pull = f"{Namespace.WsEnumeration}/Pull"
    Renew = f"{Namespace.WsEnumeration}/Renew"
    GetStatus = f"{Namespace.WsEnumeration}/GetStatus"
    Release = f"{Namespace.WsEnumeration}/Release"


class WsEventingAction(StrEnum):
    Subscribe = f"{Namespace.WsEventing}/Subscribe"
    Renew = f"{Namespace.WsEventing}/Renew"
    GetStatus = f"{Namespace.WsEventing}/GetStatus"
    Unsubscribe = f"{Namespace.WsEventing}/Unsubscribe"


class WsManagementAction(StrEnum):
    Ack = f"{WS_MANAGEMENT_PREFIX}/Ack"


class WindowsShellAction(StrEnum):
    Command = f"{Namespace.WindowsRemoteShell}/Command"
    Send = f"{Namespace.WindowsRemoteShell}/Send"
    Receive = f"{Namespace.WindowsRemoteShell}/Receive"
    Signal = f"{Namespace.WindowsRemoteShell}/Signal"


type Action = WsTransferAction | WsEnumerationAction | WsEventingAction | WsManagementAction | WindowsShellAction


class WindowsShellSignal(StrEnum):
    CtrlC = f"{Namespace.WindowsRemoteShell}/signal/ctrl_c"
    Terminate = f"{Namespace.WindowsRemoteShell}/signal/Terminate"


@dataclass
class StreamEvent:
    stream: str
    command_id: str
    content: Optional[bytes]
    finished: bool


class CommandState:
    Running = f"{Namespace.WindowsRemoteShell}/CommandState/Running"
    Done = f"{Namespace.WindowsRemoteShell}/CommandState/Done"


@dataclass
class CommandStateEvent:
    state: Optional[str]
    exit_code: Optional[int]


type ReceiveEvent = StreamEvent | CommandStateEvent

type Builder = Optional[Callable[[etree.Element], None]]


def build_soap(
    *,
    nsmap: dict[str, str],
    headers: Optional[Builder] = None,
    body: Optional[Builder] = None,
) -> etree.Element:
    root = etree.Element(Element.Envelope, nsmap=nsmap)

    el_header = etree.SubElement(root, Element.Header)
    if headers:
        headers(el_header)

    el_body = etree.SubElement(root, Element.Body)
    if body:
        body(el_body)

    return root


def build_wsman_request(
    *,
    endpoint: str,
    resource: str,
    action: Action = WsTransferAction.Get,
    selectors: Optional[dict[str, str]] = None,
    options: Optional[dict[str, str]] = None,
    body: Optional[Builder] = None,
    message_id: str = f"urn:uuid:{uuid.uuid4()}",
    locale: Optional[str] = "en-US",
    timeout: Optional[int] = None,
    max_size: Optional[int] = None,
) -> etree.Element:
    def _headers(el_header: etree.Element) -> None:
        etree.SubElement(el_header, Element.To).text = str(endpoint)

        el_reply_to = etree.SubElement(el_header, Element.ReplyTo)
        el_reply_to_address = etree.SubElement(el_reply_to, Element.Address)
        el_reply_to_address.set(Attribute.MustUnderstand, "true")
        el_reply_to_address.text = f"{Namespace.WsAddressing}/role/anonymous"

        el_action = etree.SubElement(el_header, Element.Action)
        el_action.set(Attribute.MustUnderstand, "true")
        el_action.text = action

        etree.SubElement(el_header, Element.MessageId).text = message_id

        el_resource_uri = etree.SubElement(el_header, Element.ResourceUri)
        el_resource_uri.set(Attribute.MustUnderstand, "true")
        el_resource_uri.text = resource

        if selectors:
            el_selector_set = etree.SubElement(el_header, Element.SelectorSet)
            for name, value in selectors.items():
                el_selector = etree.SubElement(el_selector_set, Element.Selector)
                el_selector.set("Name", name)
                el_selector.text = value

        if options:
            el_option_set = etree.SubElement(el_header, Element.OptionSet)
            el_option_set.set(Attribute.MustUnderstand, "true")
            for name, value in options.items():
                el_option = etree.SubElement(el_option_set, Element.Option)
                el_option.set("Name", name)
                el_option.text = value

        if locale is not None:
            el_locale = etree.SubElement(el_header, Element.Locale)
            el_locale.set(Attribute.MustUnderstand, "false")
            el_locale.set(Attribute.Lang, locale)

        if timeout is not None:
            assert timeout > 0
            etree.SubElement(el_header, Element.OperationTimeout).text = f"PT{timeout}S"

        if max_size is not None:
            assert max_size > 0
            el_max_envelope_size = etree.SubElement(el_header, Element.MaxEnvelopeSize)
            el_max_envelope_size.set(Attribute.MustUnderstand, "true")
            el_max_envelope_size.text = str(max_size)

    return build_soap(
        nsmap=Namespace.nsmap(),
        headers=_headers,
        body=body,
    )
