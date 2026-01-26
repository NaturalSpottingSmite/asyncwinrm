from base64 import b64decode, b64encode
from contextlib import suppress
from typing import Optional, Any, Collection, AsyncGenerator

import httpx
from lxml import etree

from .base import BaseConnection
from .exceptions import ProtocolError
from .protocol.soap import (
    Element,
    Namespace,
    Attribute,
    WsTransferAction,
    WindowsShellAction,
    WindowsShellSignal,
    StreamEvent,
    CommandStateEvent,
    ReceiveEvent,
)
from .protocol.resource import cim
from .shell import Shell


def _dictify_coerce(text: Optional[str]) -> Any:
    if text is None:
        return None
    if text == "false":
        return False
    if text == "true":
        return True
    with suppress(ValueError):
        return int(text)
    return text


def _dictify(root: etree._Element) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for el in root:
        name = etree.QName(el).localname
        if el.get(Attribute.Nil) == "true":
            result[name] = None
        else:
            result[name] = _dictify_coerce(el.text)
    return result


def _ensure_endpoint(endpoint: str | httpx.URL) -> httpx.URL:
    if isinstance(endpoint, httpx.URL):
        return endpoint

    is_explicit_path = endpoint.endswith("/")
    if "://" not in endpoint:
        endpoint = f"http://{endpoint}"

    is_explicit_port = ":80" in endpoint or ":443" in endpoint
    url = httpx.URL(endpoint)

    if url.port is None and not is_explicit_port:
        if url.scheme == "http":
            url = httpx.URL(url, port=5985)
        elif url.scheme == "https":
            url = httpx.URL(url, port=5986)

    if url.path == "/" and not is_explicit_path:
        url = httpx.URL(url, path="/wsman")

    if url.username or url.password:
        raise ValueError("Please use auth=httpx.BasicAuth for basic auth")

    return url


class Connection(BaseConnection):
    """High-level WinRM client."""

    def __init__(
        self,
        endpoint: str | httpx.URL,
        auth: Optional[httpx.Auth] = None,
        verify: bool = True,
        locale: Optional[str] = None,
        timeout: Optional[int] = None,
        max_envelope_size: Optional[int] = None,
    ):
        super().__init__(
            endpoint=_ensure_endpoint(endpoint),
            auth=auth,
            verify=verify,
            locale=locale,
            timeout=timeout,
            max_envelope_size=max_envelope_size,
        )

    async def get_operating_system(self) -> dict[str, Any]:
        """Get the remote operating system information."""
        body = await self.request(resource=cim("Win32_OperatingSystem"))
        data = next(iter(body), None)
        if data is None:
            raise ProtocolError("Operating system response missing service data")
        return _dictify(data)

    async def get_service(self, name: str) -> dict[str, Any]:
        """Get a service by name."""
        body = await self.request(resource=cim("Win32_Service"), selectors={"Name": name})
        data = next(iter(body), None)
        if data is None:
            raise ProtocolError("Service response missing service data")
        return _dictify(data)

    async def shell(
        self,
        directory: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        stdin: bool = True,
        stdout: bool = True,
        stderr: bool = True,
        lifetime: Optional[int] = None,
    ) -> Shell:
        def _body(el_body: etree._Element) -> None:
            el_shell = etree.SubElement(el_body, Element.Shell, nsmap={"rsp": Namespace.WindowsRemoteShell})

            if directory is not None:
                etree.SubElement(el_shell, Element.WorkingDirectory).text = directory

            if env:
                el_environment = etree.SubElement(el_shell, Element.Environment)
                for name, value in env.items():
                    el_variable = etree.SubElement(el_environment, Element.Variable)
                    el_variable.set("Name", name)
                    el_variable.text = value

            el_input_streams = etree.SubElement(el_shell, Element.InputStreams)
            if stdin:
                el_input_streams.text = "stdin"

            output_streams = ""
            if stdout:
                output_streams += " stdout"
            if stderr:
                output_streams += " stderr"
            etree.SubElement(el_shell, Element.OutputStreams).text = output_streams.strip()

            if lifetime is not None:
                etree.SubElement(el_shell, Element.Lifetime).text = f"PT{lifetime}S"

        body = await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WsTransferAction.Create,
            body=_body,
        )

        el_shell = body.find(Element.Shell)
        if el_shell is None:
            raise ProtocolError("CreateShell response missing Shell element")

        shell_id = el_shell.findtext(Element.ShellId)
        if not shell_id:
            raise ProtocolError("CreateShell response missing ShellId")

        return Shell(connection=self, id=shell_id)
