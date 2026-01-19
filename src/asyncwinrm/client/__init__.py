from typing import Optional

import httpx

from ..connection import Connection
from .shell import Shell


class Client:
    """High-level WinRM client"""

    connection: Connection

    def __init__(
        self,
        endpoint: str | httpx.URL,
        auth: httpx.Auth,
        verify: bool = True,
        locale: Optional[str] = "en-US",
        timeout: Optional[int] = 60,
    ):
        """
        :param endpoint: The endpoint to connect to. If passed as a string, a lack of URL scheme will be interpreted as
                         specifying a hostname. The default scheme is HTTP, and the default ports are 5985 for HTTP and
                         5986 for HTTPS. If no path is specified (i.e. does not end with a "/"), the path defaults to
                         "/wsman".
        :param auth: The authentication strategy to use.
        :param verify: Whether to verify the authenticity of the remote host's TLS certificate. Defaults to true.
        :param locale: The optional locale to use for human-readable messages in server responses. Defaults to en-US.
        :param timeout: The optional default timeout in seconds for requests. Defaults to 60.
        """

        if isinstance(endpoint, str):
            # workaround for httpx not storing difference between "http://example.com" and "http://example.com/"
            # (For the first case no path was specified, append /wsman. For the second case it's an explicit root path)
            is_explicit_path = endpoint.endswith("/")

            # we can't set the scheme after parsing because it gets parsed as a relative URL instead of as the host
            if "://" not in endpoint:
                endpoint = f"http://{endpoint}"

            # workaround for httpx not storing the difference between http://example.com and http://example.com:80
            is_explicit_port = ":80" in endpoint or ":443" in endpoint

            # Parse the URL
            endpoint = httpx.URL(endpoint)

            # workaround httpx having port fallback to 80/443
            if endpoint.port is None and not is_explicit_port:
                if endpoint.scheme == "http":
                    endpoint = httpx.URL(endpoint, port=5985)
                elif endpoint.scheme == "https":
                    endpoint = httpx.URL(endpoint, port=5986)

            if endpoint.path == "/" and not is_explicit_path:
                endpoint = httpx.URL(endpoint, path="/wsman")

        if endpoint.username or endpoint.password:
            raise ValueError("Please use auth=httpx.BasicAuth for basic auth")

        self.connection = Connection(
            endpoint=endpoint, auth=auth, verify=verify, locale=locale, timeout=timeout
        )

    async def shell(
        self,
        directory: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        stdin: bool = True,
        stdout: bool = True,
        stderr: bool = True,
        lifetime: Optional[int] = None,
    ) -> Shell:
        data = await self.connection.create_shell(
            directory=directory,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            lifetime=lifetime,
        )
        return Shell(connection=self.connection, id=data["ShellId"])
