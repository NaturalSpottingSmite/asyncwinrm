from lxml import etree

from .namespace import Namespace
from ..uri import cim


class SOAPElement:
    Envelope = etree.QName(Namespace.SOAP, "Envelope")
    Header = etree.QName(Namespace.SOAP, "Header")
    Body = etree.QName(Namespace.SOAP, "Body")
    Fault = etree.QName(Namespace.SOAP, "Fault")
    Reason = etree.QName(Namespace.SOAP, "Reason")
    Text = etree.QName(Namespace.SOAP, "Text")
    Code = etree.QName(Namespace.SOAP, "Code")
    Value = etree.QName(Namespace.SOAP, "Value")


class WSAddressingElement:
    To = etree.QName(Namespace.WSAddressing, "To")
    Action = etree.QName(Namespace.WSAddressing, "Action")
    Address = etree.QName(Namespace.WSAddressing, "Address")
    ReplyTo = etree.QName(Namespace.WSAddressing, "ReplyTo")
    MessageID = etree.QName(Namespace.WSAddressing, "MessageID")
    ReferenceParameters = etree.QName(Namespace.WSAddressing, "ReferenceParameters")


class WSTransferElement:
    ResourceCreated = etree.QName(Namespace.WSTransfer, "ResourceCreated")


class WSManagementElement:
    ResourceURI = etree.QName(Namespace.WSManagement, "ResourceURI")
    MaxEnvelopeSize = etree.QName(Namespace.WSManagement, "MaxEnvelopeSize")
    Locale = etree.QName(Namespace.WSManagement, "Locale")
    DataLocale = etree.QName(Namespace.WSManagement, "DataLocale")
    SelectorSet = etree.QName(Namespace.WSManagement, "SelectorSet")
    Selector = etree.QName(Namespace.WSManagement, "Selector")
    OptionSet = etree.QName(Namespace.WSManagement, "OptionSet")
    Option = etree.QName(Namespace.WSManagement, "Option")
    OperationTimeout = etree.QName(Namespace.WSManagement, "OperationTimeout")
    OptimizeOperation = etree.QName(Namespace.WSManagement, "OptimizeOperation")


class WSManagementIdentityElement:
    Identify = etree.QName(Namespace.WSManagementIdentity, "Identify")
    IdentifyResponse = etree.QName(Namespace.WSManagementIdentity, "IdentifyResponse")
    ProtocolVersion = etree.QName(Namespace.WSManagementIdentity, "ProtocolVersion")
    ProductVendor = etree.QName(Namespace.WSManagementIdentity, "ProductVendor")
    ProductVersion = etree.QName(Namespace.WSManagementIdentity, "ProductVersion")
    SecurityProfiles = etree.QName(Namespace.WSManagementIdentity, "SecurityProfiles")
    SecurityProfileName = etree.QName(Namespace.WSManagementIdentity, "SecurityProfileName")


class WSEnumerationElement:
    Enumerate = etree.QName(Namespace.WSEnumeration, "Enumerate")
    EnumerateResponse = etree.QName(Namespace.WSEnumeration, "EnumerateResponse")
    EnumerationContext = etree.QName(Namespace.WSEnumeration, "EnumerationContext")
    MaxElements = etree.QName(Namespace.WSEnumeration, "MaxElements")

    Pull = etree.QName(Namespace.WSEnumeration, "Pull")
    PullResponse = etree.QName(Namespace.WSEnumeration, "PullResponse")
    Items = etree.QName(Namespace.WSEnumeration, "Items")
    EndOfSequence = etree.QName(Namespace.WSEnumeration, "EndOfSequence")

    Release = etree.QName(Namespace.WSEnumeration, "Release")


class RemoteShellElement:
    Shell = etree.QName(Namespace.WindowsRemoteShell, "Shell")
    ShellID = etree.QName(Namespace.WindowsRemoteShell, "ShellId")
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
    CommandID = etree.QName(Namespace.WindowsRemoteShell, "CommandId")
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


class CIMElement:
    OperatingSystem = _make_cim_element("Win32_OperatingSystem")
    Service = _make_cim_element("Win32_Service")


__all__ = [
    "SOAPElement",
    "WSAddressingElement",
    "WSTransferElement",
    "WSManagementElement",
    "WSManagementIdentityElement",
    "WSEnumerationElement",
    "RemoteShellElement",
    "CIMElement",
]
