from httpx import Auth
from httpx_ntlm import HttpNtlmAuth


def ntlm(username: str, password: str) -> Auth:
    """
    Creates a new NTLM auth handler.

    :param username: The username to use.
    :param password: The password to use.
    """
    return HttpNtlmAuth(username, password)


__all__ = ["ntlm"]
