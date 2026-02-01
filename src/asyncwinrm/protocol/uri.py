WINDOWS_WSMAN_PREFIX = "http://schemas.microsoft.com/wbem/wsman/1"


def uri(*args: str) -> str:
    """
    Construct a resource URI for a WS-Man resource.

    :param args: The components of the URI. They will be joined together with a "/" and appended to the following URL:
                 http://schemas.microsoft.com/wbem/wsman/1
    """
    return f"{WINDOWS_WSMAN_PREFIX}/{'/'.join(args)}"


def wmi(*args: str, namespace: str = "default") -> str:
    """
    Construct a resource URI for a WMI resource in root\\{namespace}.

    :param args: The components of the URI. They will be joined together with a "/" and appended to the following URL:
                 http://schemas.microsoft.com/wbem/wsman/1/wmi/root/<namespace>
    :param namespace: The WMI namespace to target. Defaults to "default".
    """
    return uri("wmi", "root", namespace, *args)


def cim(*args: str) -> str:
    """
    Construct a resource URI for a CIM resource.

    :param args: The components of the URI. They will be joined together with a "/" and appended to the following URL:
                 http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2
    """
    return wmi(*args, namespace="cimv2")


__all__ = ["uri", "wmi", "cim"]
