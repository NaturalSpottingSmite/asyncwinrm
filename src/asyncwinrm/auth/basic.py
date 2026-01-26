from httpx import Auth, BasicAuth


def basic(username: str, password: str) -> Auth:
    """
    Creates a new Basic auth handler.

    :param username: The username to use.
    :param password: The password to use.
    """
    return BasicAuth(username, password)


__all__ = ["basic"]
