from lxml import etree

from .namespace import Namespace


class XmlAttribute:
    Lang = etree.QName(Namespace.Xml, "lang")


class XsiAttribute:
    Nil = etree.QName(Namespace.Xsi, "nil")


class SoapAttribute:
    MustUnderstand = etree.QName(Namespace.Soap, "mustUnderstand")


__all__ = [
    "XmlAttribute",
    "XsiAttribute",
    "SoapAttribute",
]
