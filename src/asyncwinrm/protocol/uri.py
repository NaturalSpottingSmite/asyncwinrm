WINDOWS_WSMAN_PREFIX = "http://schemas.microsoft.com/wbem/wsman/1"


def uri(*args: str) -> str:
    """
    Construct a resource URI for a WS-Man resource.

    :param args: The components of the URI. They will be joined together with a "/" and appended to the following URL:
                 http://schemas.microsoft.com/wbem/wsman/1
    """
    return f"{WINDOWS_WSMAN_PREFIX}/{'/'.join(args)}"


def cim(*args: str) -> str:
    """
    Construct a resource URI for a CIM resource.

    :param args: The components of the URI. They will be joined together with a "/" and appended to the following URL:
                 http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2
    """
    return uri("wmi", "root", "cimv2", *args)


__all__ = ["uri", "cim"]
