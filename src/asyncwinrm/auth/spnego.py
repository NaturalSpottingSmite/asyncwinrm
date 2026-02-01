import asyncio
import base64
import os
import tempfile
import threading
from textwrap import dedent
from typing import Generator, AsyncGenerator, Optional

import spnego
from httpx import Auth, Request, Response, Headers

from .encryption import encrypt_message, decrypt_response_content, SOAP_CONTENT_TYPE


class SPNEGOAuth(Auth):
    username: str
    password: str
    hostname: str
    protocol: str
    service: str

    # Since the context depends on the value of previous requests to drive its internal state machine, we *must* make
    # sure that requests come in serially. So we only use the context behind these locks, to ensure that any other
    # requests coming in while another request is being processed have to wait. This does mean that it's impossible to
    # send requests in parallel using one instance of SPNEGOAuth, but this is kind of how SPNEGO works. You can always
    # make multiple SPNEGOAuth instances and use them with multiple clients if you really need to do things in parallel.
    _lock: threading.Lock
    _async_lock: asyncio.Lock

    _context: Optional[spnego.ContextProxy]

    def __init__(
        self,
        username: str,
        password: str,
        *,
        protocol: str = "negotiate",
        hostname: str | None = None,
        service: str = "HTTP",
    ) -> None:
        self.username = username
        self.password = password
        self.hostname = hostname or "unspecified"
        self.protocol = protocol
        self.service = service
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._context = spnego.client(
            self.username,
            self.password,
            hostname=self.hostname,
            service=self.service,
            protocol=self.protocol,
        )

    def _allowed_schemes(self) -> set[str]:
        if self.protocol == "kerberos":
            return {"negotiate", "kerberos"}
        if self.protocol == "ntlm":
            return {"negotiate", "ntlm"}
        return {"negotiate", "kerberos", "ntlm"}

    def _decode_header(self, response: Response) -> bytes | None:
        allowed = self._allowed_schemes()
        for header in response.headers.get_list("www-authenticate"):
            parts = header.split(" ", 1)
            if parts[0].lower() not in allowed:
                continue
            if len(parts) == 2 and parts[1]:
                return base64.b64decode(parts[1])
        return None

    @staticmethod
    def _set_auth_header(request: Request, token: bytes) -> None:
        request.headers["Authorization"] = f"Negotiate {base64.b64encode(token).decode('ascii')}"

    @staticmethod
    def _clone_request(request: Request) -> Request:
        return Request(
            request.method,
            request.url,
            headers=request.headers.copy(),
            content=request.content,
        )

    @staticmethod
    def _clone_request_with_content(request: Request, content: bytes, headers: Optional[Headers] = None) -> Request:
        return Request(
            request.method,
            request.url,
            headers=request.headers.copy() if headers is None else headers,
            content=content,
        )

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        with self._lock:
            out_token = self._context.step()
            if out_token is not None:
                self._set_auth_header(request, out_token)
            response = yield request
            while not self._context.complete:
                in_token = self._decode_header(response)
                if in_token is None:
                    break
                response.read()
                out_token = self._context.step(in_token)
                if out_token is None:
                    break
                request = self._clone_request(response.request)
                self._set_auth_header(request, out_token)
                response = yield request

    async def async_auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        async with self._async_lock:
            out_token = self._context.step()
            if out_token is not None:
                self._set_auth_header(request, out_token)
            response = yield request
            while not self._context.complete:
                in_token = self._decode_header(response)
                if in_token is None:
                    break
                await response.aread()
                out_token = self._context.step(in_token)
                if out_token is None:
                    break
                request = self._clone_request(response.request)
                self._set_auth_header(request, out_token)
                response = yield request


class SPNEGOEncryptedAuth(SPNEGOAuth):
    def _build_preflight_request(self, request: Request, token: bytes) -> Request:
        headers = request.headers.copy()
        headers["content-length"] = "0"
        headers.setdefault("content-type", SOAP_CONTENT_TYPE)
        preflight = self._clone_request_with_content(request, b"", headers=headers)
        self._set_auth_header(preflight, token)
        return preflight

    def _build_encrypted_request(self, request: Request, context: spnego.ContextProxy) -> Request:
        encrypted_body, encryption_headers = encrypt_message(context, request.content)
        headers = request.headers.copy()
        headers.update(encryption_headers)
        return self._clone_request_with_content(request, encrypted_body, headers=headers)

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        with self._lock:
            in_token: bytes | None = None
            while not self._context.complete:
                out_token = self._context.step(in_token)
                if out_token is None:
                    break
                response = yield self._build_preflight_request(request, out_token)
                in_token = self._decode_header(response)
                response.read()
                if in_token is None:
                    break

            encrypted_request = self._build_encrypted_request(request, self._context)
            response = yield encrypted_request
            content = response.read()
            decrypted = decrypt_response_content(self._context, content, response.headers.get("Content-Type", ""))
            response._content = decrypted

    async def async_auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        async with self._async_lock:
            in_token: bytes | None = None
            while not self._context.complete:
                out_token = self._context.step(in_token)
                if out_token is None:
                    break
                response = yield self._build_preflight_request(request, out_token)
                in_token = self._decode_header(response)
                await response.aread()
                if in_token is None:
                    break

            encrypted_request = self._build_encrypted_request(request, self._context)
            response = yield encrypted_request
            content = await response.aread()
            decrypted = decrypt_response_content(self._context, content, response.headers.get("Content-Type", ""))
            response._content = decrypted


def negotiate(username: str, password: str, *, encrypted: bool = True) -> Auth:
    """
    Creates a new Negotiate auth handler.

    :param username: The username to use.
    :param password: The password to use.
    :param encrypted: Whether to use WinRM message-level encryption. Defaults to True, set to False when using TLS.
    """
    return SPNEGOEncryptedAuth(username, password) if encrypted else SPNEGOAuth(username, password)


def _write_krb5_conf(realm: str, address: str) -> str:
    """
    Write a hacky krb5.conf that allows reaching a KDC without being able to resolve its DNS name

    :param realm: The realm to use.
    :param address: The address of the Key Distribution Center (KDC) to use for this realm.
    :return: Path to the written krb5.conf that can be set to KRB5_CONFIG to make Kerberos use the given address to
             contact the KDC.
    """
    realm_upper = realm.upper()
    realm_lower = realm.lower()
    content = dedent(
        f"""
        [libdefaults]
        default_realm = {realm_upper}
        dns_lookup_kdc = false
        dns_lookup_realm = false
        [realms]
        {realm_upper} = {{
         kdc = {address}
        }}
        [domain_realm]
        .{realm_lower} = {realm_upper}
        {realm_lower} = {realm_upper}
    """
    )
    temp = tempfile.NamedTemporaryFile(prefix="krb5.", suffix=".conf", delete=False)
    temp.write(content.encode("utf-8"))
    temp.close()
    return temp.name


def kerberos(
    username: str,
    password: str,
    *,
    realm: str,
    address: str | None = None,
    hostname: str | None = None,
    encrypted: bool = True,
) -> Auth:
    """
    Creates a new Kerberos auth handler.

    :param username: The username to use.
    :param password: The password to use.
    :param realm: The realm/domain of the user.
    :param address: The address of the Key Distribution Center (KDC). If it does not match the realm, a temporary
                    Kerberos configuration will be written out and used, to allow authenticating without being able to
                    resolve the realm's hostname. Defaults to the realm.
    :param hostname: The hostname of the target machine to build the HTTP SPN for. Different from the domain/realm (this
                     is the hostname of the machine providing the service e.g. WinRM, as opposed to the domain name).
    :param encrypted: Whether to use WinRM message-level encryption. Defaults to True, set to False when using TLS.
    """
    if "@" in username:
        raise ValueError("Please use the realm=... parameter to specify the realm/domain for kerberos()")

    principal = f"{username}@{realm}"
    host = address or realm

    if host != realm and "KRB5_CONFIG" not in os.environ:
        os.environ["KRB5_CONFIG"] = _write_krb5_conf(realm, host)

    spn_host = hostname or realm

    return (
        SPNEGOEncryptedAuth(principal, password, protocol="kerberos", hostname=spn_host)
        if encrypted
        else SPNEGOAuth(principal, password, protocol="kerberos", hostname=spn_host)
    )


__all__ = ["SPNEGOAuth", "SPNEGOEncryptedAuth", "negotiate", "kerberos"]
