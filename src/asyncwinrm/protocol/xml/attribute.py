from lxml import etree

from .namespace import Namespace


class XMLAttribute:
    Lang = etree.QName(Namespace.Xml, "lang")


class XSIAttribute:
    Nil = etree.QName(Namespace.Xsi, "nil")


class SOAPAttribute:
    MustUnderstand = etree.QName(Namespace.SOAP, "mustUnderstand")


__all__ = [
    "XMLAttribute",
    "XSIAttribute",
    "SOAPAttribute",
]
