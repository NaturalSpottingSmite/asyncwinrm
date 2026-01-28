from lxml import etree

from .namespace import Namespace
from ..uri import cim


class SoapElement:
    Envelope = etree.QName(Namespace.Soap, "Envelope")
    Header = etree.QName(Namespace.Soap, "Header")
    Body = etree.QName(Namespace.Soap, "Body")
    Fault = etree.QName(Namespace.Soap, "Fault")
    Reason = etree.QName(Namespace.Soap, "Reason")
    Text = etree.QName(Namespace.Soap, "Text")
    Code = etree.QName(Namespace.Soap, "Code")
    Value = etree.QName(Namespace.Soap, "Value")


class WsAddressingElement:
    To = etree.QName(Namespace.WsAddressing, "To")
    Action = etree.QName(Namespace.WsAddressing, "Action")
    Address = etree.QName(Namespace.WsAddressing, "Address")
    ReplyTo = etree.QName(Namespace.WsAddressing, "ReplyTo")
    MessageId = etree.QName(Namespace.WsAddressing, "MessageID")
    ReferenceParameters = etree.QName(Namespace.WsAddressing, "ReferenceParameters")


class WsManagementElement:
    ResourceUri = etree.QName(Namespace.WsManagement, "ResourceURI")
    MaxEnvelopeSize = etree.QName(Namespace.WsManagement, "MaxEnvelopeSize")
    Locale = etree.QName(Namespace.WsManagement, "Locale")
    DataLocale = etree.QName(Namespace.WsManagement, "DataLocale")
    SelectorSet = etree.QName(Namespace.WsManagement, "SelectorSet")
    Selector = etree.QName(Namespace.WsManagement, "Selector")
    OptionSet = etree.QName(Namespace.WsManagement, "OptionSet")
    Option = etree.QName(Namespace.WsManagement, "Option")
    OperationTimeout = etree.QName(Namespace.WsManagement, "OperationTimeout")
    OptimizeOperation = etree.QName(Namespace.WsManagement, "OptimizeOperation")


class WsManagementIdentityElement:
    Identify = etree.QName(Namespace.WsManagementIdentity, "Identify")
    IdentifyResponse = etree.QName(Namespace.WsManagementIdentity, "IdentifyResponse")
    ProtocolVersion = etree.QName(Namespace.WsManagementIdentity, "ProtocolVersion")
    ProductVendor = etree.QName(Namespace.WsManagementIdentity, "ProductVendor")
    ProductVersion = etree.QName(Namespace.WsManagementIdentity, "ProductVersion")
    SecurityProfiles = etree.QName(Namespace.WsManagementIdentity, "SecurityProfiles")
    SecurityProfileName = etree.QName(Namespace.WsManagementIdentity, "SecurityProfileName")


class WsEnumerationElement:
    Enumerate = etree.QName(Namespace.WsEnumeration, "Enumerate")
    EnumerateResponse = etree.QName(Namespace.WsEnumeration, "EnumerateResponse")
    EnumerationContext = etree.QName(Namespace.WsEnumeration, "EnumerationContext")
    MaxElements = etree.QName(Namespace.WsEnumeration, "MaxElements")

    Pull = etree.QName(Namespace.WsEnumeration, "Pull")
    PullResponse = etree.QName(Namespace.WsEnumeration, "PullResponse")
    Items = etree.QName(Namespace.WsEnumeration, "Items")
    EndOfSequence = etree.QName(Namespace.WsEnumeration, "EndOfSequence")

    Release = etree.QName(Namespace.WsEnumeration, "Release")


class RemoteShellElement:
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


def _make_cim_element(name: str) -> etree.QName:
    return etree.QName(cim(name), name)


class CimElement:
    OperatingSystem = _make_cim_element("Win32_OperatingSystem")
    Service = _make_cim_element("Win32_Service")


__all__ = [
    "SoapElement",
    "WsAddressingElement",
    "WsManagementElement",
    "WsManagementIdentityElement",
    "WsEnumerationElement",
    "RemoteShellElement",
    "CimElement",
]
