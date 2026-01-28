from contextlib import suppress
from typing import Optional, Any

import httpx
from lxml import etree

from .wsman import WsManagementClient
from ..exceptions import ProtocolError
from ..protocol.uri import cim
from ..protocol.action import WsTransferAction
from ..protocol.xml.attribute import XsiAttribute
from ..shell import Shell
from ..protocol.xml.element import CimElement, RemoteShellElement
from ..protocol.xml.namespace import Namespace


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


def dictify(root: etree.Element) -> dict[str, Any]:
    """Tries to convert an XML element to a Python dictionary."""
    result: dict[str, Any] = {}
    for el in root:
        name = etree.QName(el).localname
        if el.get(XsiAttribute.Nil) == "true":
            result[name] = None
        else:
            result[name] = _dictify_coerce(el.text)
    return result


def _parse_endpoint(endpoint: str | httpx.URL) -> httpx.URL:
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


class WinRmClient(WsManagementClient):
    """High-level WinRM client"""

    def __init__(
        self,
        endpoint: str | httpx.URL,
        *,
        auth: Optional[httpx.Auth] = None,
        verify: bool = True,
        locale: str = "en-US",
        timeout: Optional[int] = None,
        max_envelope_size: int = 512 * 1024,
    ):
        ep = _parse_endpoint(endpoint)
        client = httpx.AsyncClient(
            base_url=ep,
            auth=auth,
            verify=verify,
            headers={"Content-Type": "application/soap+xml; charset=UTF-8"},
        )
        super().__init__(client, ep, locale=locale, timeout=timeout, max_envelope_size=max_envelope_size)

    async def get_cim_object(self, obj: etree.QName, *, name: Optional[str] = None):
        """Get a CIM object."""
        selectors = {}
        if name is not None:
            selectors["Name"] = name
        resp = await self.get(resource_uri=cim(obj.localname), data_element=obj, selectors=selectors)
        return dictify(resp.data)

    async def get_operating_system(self) -> dict[str, Any]:
        """Get the remote operating system information."""
        return await self.get_cim_object(CimElement.OperatingSystem)

    async def get_service(self, name: str) -> dict[str, Any]:
        """Get a service by name."""
        return await self.get_cim_object(CimElement.Service, name=name)

    async def shell(
        self,
        directory: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        stdin: bool = True,
        stdout: bool = True,
        stderr: bool = True,
        lifetime: Optional[int] = None,
    ) -> Shell:
        body = etree.Element(RemoteShellElement.Shell, nsmap={"rsp": Namespace.WindowsRemoteShell})

        if directory is not None:
            etree.SubElement(body, RemoteShellElement.WorkingDirectory).text = directory

        if env:
            el_environment = etree.SubElement(body, RemoteShellElement.Environment)
            for name, value in env.items():
                el_variable = etree.SubElement(el_environment, RemoteShellElement.Variable)
                el_variable.set("Name", name)
                el_variable.text = value

        el_input_streams = etree.SubElement(body, RemoteShellElement.InputStreams)
        if stdin:
            el_input_streams.text = "stdin"

        output_streams = ""
        if stdout:
            output_streams += " stdout"
        if stderr:
            output_streams += " stderr"
        etree.SubElement(body, RemoteShellElement.OutputStreams).text = output_streams.strip()

        if lifetime is not None:
            etree.SubElement(body, RemoteShellElement.Lifetime).text = f"PT{lifetime}S"

        response = await self.request(
            WsTransferAction.Create,
            body,
            resource_uri=f"{Namespace.WindowsRemoteShell}/cmd",
            data_element=RemoteShellElement.Shell,
        )

        shell_id = response.data.findtext(RemoteShellElement.ShellId)
        if not shell_id:
            raise ProtocolError("CreateShell response missing ShellId")

        return Shell(client=self, id=shell_id)


__all__ = ["WinRmClient"]
