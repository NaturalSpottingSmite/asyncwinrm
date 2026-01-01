import uuid
from base64 import b64decode, b64encode
from contextlib import suppress
from typing import Optional, Callable, Any, AsyncGenerator

import httpx
from lxml import etree

from .schema import (
    Element,
    WindowsShellSignal,
    Namespace,
    Attribute,
    WsTransferAction,
    WindowsShellAction,
    StreamEvent,
    CommandStateEvent,
    cim,
    Action,
)

type Builder = Optional[Callable[[etree._Element], None]]


def build_request(
    *,
    endpoint: str,
    resource: str,
    action: Action = WsTransferAction.Get,
    selectors: Optional[dict[str, str]] = None,
    options: Optional[dict[str, str]] = None,
    body: Optional[Builder] = None,
    message_id: str = f"urn:uuid:{uuid.uuid4()}",
    locale: Optional[str] = "en-US",
    timeout: Optional[int] = None,
    max_size: Optional[int] = None,
) -> bytes:
    """
    Construct a WS-Management SOAP request.

    :param endpoint: The endpoint where this request is directed to.
    :param resource: The resource URI to access.
    :param action: The action to take on the resource specified (defaults to Get).
    :param selectors: An optional dictionary of selectors.
    :param options: An optional dictionary of options.
    :param body: An optional builder function to create the request body.
    :param message_id: A unique identifier for this message (defaults to a random UUIDv4 compliant with RFC 4122).
    :param locale: An optional locale for human-readable strings in the response (defaults to en-US).
    :param timeout: An optional timeout for the response in seconds (defaults to None).
    :param max_size: An optional maximum size limit for the whole response envelope in octets (defaults to None).
    :returns: The serialized SOAP request envelope as bytes.
    """
    root = etree.Element(Element.Envelope, nsmap=Namespace.nsmap())

    # Headers ====================================

    el_header = etree.SubElement(root, Element.Header)

    etree.SubElement(el_header, Element.To).text = str(endpoint)

    el_reply_to = etree.SubElement(el_header, Element.ReplyTo)
    el_reply_to_address = etree.SubElement(el_reply_to, Element.Address)
    el_reply_to_address.set(Attribute.MustUnderstand, "true")
    el_reply_to_address.text = f"{Namespace.WsAddressing}/role/anonymous"

    el_action = etree.SubElement(el_header, Element.Action)
    el_action.set(Attribute.MustUnderstand, "true")
    el_action.text = action

    etree.SubElement(el_header, Element.MessageId).text = message_id

    el_resource_uri = etree.SubElement(el_header, Element.ResourceUri)
    el_resource_uri.set(Attribute.MustUnderstand, "true")
    el_resource_uri.text = resource

    if selectors is not None and len(selectors) > 0:
        el_selector_set = etree.SubElement(el_header, Element.SelectorSet)
        for name, value in selectors.items():
            el_selector = etree.SubElement(el_selector_set, Element.Selector)
            el_selector.set("Name", name)
            el_selector.text = value

    if options is not None and len(options) > 0:
        el_option_set = etree.SubElement(el_header, Element.OptionSet)
        el_option_set.set(Attribute.MustUnderstand, "true")
        for name, value in options.items():
            el_option = etree.SubElement(el_option_set, Element.Option)
            el_option.set("Name", name)
            el_option.text = value

    if locale is not None:
        el_locale = etree.SubElement(el_header, Element.Locale)
        el_locale.set(Attribute.MustUnderstand, "false")
        el_locale.set(Attribute.Lang, locale)

    if timeout is not None:
        assert timeout > 0
        etree.SubElement(el_header, Element.OperationTimeout).text = f"PT{timeout}S"

    if max_size is not None:
        assert max_size > 0
        el_max_envelope_size = etree.SubElement(el_header, Element.MaxEnvelopeSize)
        el_max_envelope_size.set(Attribute.MustUnderstand, "true")
        el_max_envelope_size.text = str(max_size)

    # Body =======================================

    el_body = etree.SubElement(root, Element.Body)

    if body:
        body(el_body)

    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def parse_response(resp: httpx.Response) -> AsyncGenerator[etree._Element]:
    parser = etree.XMLPullParser(tag=Element.Envelope)
    print(resp)
    print(resp.headers)
    async for chunk in resp.aiter_bytes():
        print(chunk.decode("utf-8"), end="")
        parser.feed(chunk)

        for event, elem in parser.read_events():
            if elem.tag != Element.Envelope:
                continue

            el_header = elem.find(Element.Header)
            el_body = elem.find(Element.Body)

            if not resp.is_success:
                el_fault = el_body.find(Element.Fault)
                el_fault_reason = el_fault.find(Element.Reason)
                el_fault_reason_text = el_fault_reason.find(Element.Text)

                raise ValueError(el_fault_reason_text.text)

            # at this point we should be OK
            resp.raise_for_status()

            el_header_action = el_header.find(Element.Action)
            print(el_header_action.text)
            yield el_body

    parser.close()


def dictify_coerce(text: str) -> Any:
    if text == "false":
        return False
    elif text == "true":
        return True
    else:
        with suppress(ValueError):
            return int(text)

        return text


def dictify(root: etree._Element) -> dict[str, Any]:
    result = {}

    for el in root:
        name = etree.QName(el).localname
        if el.get(Attribute.Nil) == "true":
            result[name] = None
        else:
            result[name] = dictify_coerce(el.text)

    return result


type ReceiveEvent = StreamEvent | CommandStateEvent


class WinRmClient:
    """Low-level WinRM protocol client"""

    endpoint: httpx.URL
    http: httpx.AsyncClient

    locale: Optional[str]
    timeout: Optional[int]

    def __init__(
        self,
        endpoint: str | httpx.URL,
        auth: httpx.Auth,
        verify: bool = True,
        locale: Optional[str] = "en-US",
        timeout: Optional[int] = 60,
    ):
        self.locale = locale
        self.timeout = timeout

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

        self.endpoint = endpoint
        self.http = httpx.AsyncClient(
            base_url=endpoint,
            auth=auth,
            verify=verify,
            headers={
                "Content-Type": "application/soap+xml; charset=UTF-8",
            },
        )

    async def request(
        self,
        *,
        resource: str,
        action: Action = WsTransferAction.Get,
        selectors: Optional[dict[str, str]] = None,
        body: Optional[Builder] = None,
        timeout: Optional[int] = None,
    ):
        content = build_request(
            endpoint=str(self.endpoint),
            resource=resource,
            action=action,
            selectors=selectors,
            body=body,
            locale=self.locale,
            timeout=timeout or self.timeout,
        )

        # print(content.decode("utf-8"))
        # resp = await self.http.post("", content=content)
        req = self.http.build_request("POST", "", content=content)
        print(req)
        print(req.headers)
        resp = await self.http.send(req)
        async for body in parse_response(resp):
            return body
        raise ValueError("no response envelope")

    async def get_service(self, name: str) -> dict[str, Any]:
        """Get a service by its name"""
        res = await self.request(
            resource=cim("Win32_Service"), selectors={"Name": name}
        )
        return dictify(res[0])

    async def create_shell(
        self,
        directory: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        stdin: bool = True,
        stdout: bool = True,
        stderr: bool = True,
        lifetime: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a shell"""

        def _body(el_body: etree._Element):
            el_shell = etree.SubElement(
                el_body, Element.Shell, nsmap={"rsp": Namespace.WindowsRemoteShell}
            )

            if directory is not None:
                etree.SubElement(el_shell, Element.WorkingDirectory).text = directory

            if env is not None and len(env) > 0:
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
            etree.SubElement(el_shell, Element.OutputStreams).text = (
                output_streams.strip()
            )

            if lifetime is not None:
                etree.SubElement(el_shell, Element.Lifetime).text = f"PT{lifetime}S"

        res = await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WsTransferAction.Create,
            body=_body,
        )

        return dictify(res.find(Element.Shell))

    async def delete_shell(self, shell_id: str) -> None:
        """Delete a shell"""
        await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WsTransferAction.Delete,
            selectors={"ShellId": shell_id},
        )

    async def command_shell(
        self, shell_id: str, command: str, arguments: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """Command a shell"""

        def _body(el_body: etree._Element):
            el_cl = etree.SubElement(
                el_body,
                Element.CommandLine,
                nsmap={"rsp": Namespace.WindowsRemoteShell},
            )
            etree.SubElement(el_cl, Element.Command).text = command
            if arguments is not None:
                for arg in arguments:
                    etree.SubElement(el_cl, Element.Arguments).text = arg

        res = await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Command,
            selectors={"ShellId": shell_id},
            body=_body,
        )

        return dictify(res.find(Element.CommandResponse))

    async def receive_shell(
        self, shell_id: str, command_id: str, stdout: bool = True, stderr: bool = True
    ) -> AsyncGenerator[ReceiveEvent, None]:
        """Receive a shell"""

        def _body(el_body: etree._Element):
            el_receive = etree.SubElement(
                el_body, Element.Receive, nsmap={"rsp": Namespace.WindowsRemoteShell}
            )

            el_desired_stream = etree.SubElement(el_receive, Element.DesiredStream)
            el_desired_stream.set("CommandId", command_id)
            desired_stream = ""
            if stdout:
                desired_stream += " stdout"
            if stderr:
                desired_stream += " stderr"
            el_desired_stream.text = desired_stream.strip()

        res = await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Receive,
            selectors={"ShellId": shell_id},
            body=_body,
        )

        for el in res.find(Element.ReceiveResponse):
            if el.tag == Element.Stream:
                yield StreamEvent(
                    stream=el.get("Name"),
                    command_id=el.get("CommandId"),
                    content=b64decode(el.text) if el.text else None,
                    finished=el.get("End") == "true",
                )
            elif el.tag == Element.CommandState:
                # print(etree.tostring(res, pretty_print=True).decode("utf-8"))
                el_exit_code = el.find(Element.ExitCode)
                yield CommandStateEvent(
                    state=el.get("State"),
                    exit_code=(
                        int(el_exit_code.text) if el_exit_code is not None else None
                    ),
                )
            else:
                # TODO: look at the actual possible child types, is there anything else?
                print("dont know what it is :(")
                print(el.tag)
                print(etree.tostring(res, pretty_print=True).decode("utf-8"))

    async def signal_shell(
        self, shell_id: str, command_id: str, signal: WindowsShellSignal
    ) -> None:
        """Signal a shell"""

        def _body(el_body: etree._Element):
            el_signal = etree.SubElement(
                el_body, Element.Signal, nsmap={"rsp": Namespace.WindowsRemoteShell}
            )
            el_signal.set("CommandId", command_id)
            etree.SubElement(el_signal, Element.Code).text = signal

        await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Signal,
            selectors={"ShellId": shell_id},
            body=_body,
        )

    async def send_shell(self, shell_id: str, command_id: str, data: bytes) -> None:
        """Send a shell"""

        def _body(el_body: etree._Element):
            el_send = etree.SubElement(
                el_body, Element.Send, nsmap={"rsp": Namespace.WindowsRemoteShell}
            )
            el_stream = etree.SubElement(el_send, Element.Stream)
            el_stream.set("CommandId", command_id)
            el_stream.set("Name", "stdin")
            el_stream.text = b64encode(data)

        await self.request(
            resource=f"{Namespace.WindowsRemoteShell}/cmd",
            action=WindowsShellAction.Send,
            selectors={"ShellId": shell_id},
            body=_body,
        )
