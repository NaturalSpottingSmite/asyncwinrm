import struct

import httpx
import spnego

from ..exceptions import EncryptionError

BOUNDARY = "Encrypted Boundary"
MIME_BOUNDARY = f"--{BOUNDARY}".encode("ascii")
PROTOCOL = "application/HTTP-SPNEGO-session-encrypted"
CONTENT_TYPE = f'multipart/encrypted;protocol="{PROTOCOL}";boundary="{BOUNDARY}"'
SOAP_CONTENT_TYPE = "application/soap+xml; charset=UTF-8"


def _encrypt_message(context: spnego.ContextProxy, message: bytes) -> bytes:
    message_length = str(len(message))
    wrapped = context.wrap_winrm(message)
    header_length = struct.pack("<i", len(wrapped.header))

    payload = (
        MIME_BOUNDARY + b"\r\n"
        b"\tContent-Type: " + PROTOCOL.encode("ascii") + b"\r\n"
        b"\tOriginalContent: type=application/soap+xml;charset=UTF-8;Length="
        + message_length.encode("ascii")
        + b"\r\n"
        + MIME_BOUNDARY
        + b"\r\n"
        b"\tContent-Type: application/octet-stream\r\n" + header_length + wrapped.header + wrapped.data
    )
    return payload


def _decrypt_message(context: spnego.ContextProxy, encrypted_data: bytes) -> bytes:
    if len(encrypted_data) < 4:
        raise EncryptionError("Encrypted payload is too short to contain header length")

    header_length = struct.unpack("<i", encrypted_data[:4])[0]
    if header_length < 0 or len(encrypted_data) < 4 + header_length:
        raise EncryptionError("Encrypted payload header length is invalid")

    header = encrypted_data[4 : 4 + header_length]
    data = encrypted_data[4 + header_length :]
    return context.unwrap_winrm(header, data)


def _decrypt_response(context: spnego.ContextProxy, content: bytes) -> bytes:
    parts = content.split(MIME_BOUNDARY + b"\r\n")
    parts = list(filter(None, parts))
    message = b""

    for i in range(0, len(parts), 2):
        if i + 1 >= len(parts):
            raise EncryptionError("Encrypted response is missing payload part")

        header = parts[i].strip()
        payload = parts[i + 1]

        try:
            expected_length = int(header.split(b"Length=")[1])
        except (IndexError, ValueError) as exc:
            raise EncryptionError("Encrypted response missing Length header") from exc

        if payload.endswith(MIME_BOUNDARY + b"--\r\n"):
            payload = payload[: -len(MIME_BOUNDARY + b"--\r\n")]

        encrypted_data = payload.replace(b"\tContent-Type: application/octet-stream\r\n", b"")
        decrypted_message = _decrypt_message(context, encrypted_data)

        if len(decrypted_message) != expected_length:
            raise EncryptionError("Encrypted response length does not match expected size")
        message += decrypted_message

    return message


def encrypt_message(context: spnego.ContextProxy, message: bytes) -> tuple[bytes, httpx.Headers]:
    encrypted_message = _encrypt_message(context, message)
    encrypted_message += MIME_BOUNDARY + b"--\r\n"
    headers = httpx.Headers(
        {
            "Content-Type": CONTENT_TYPE,
            "Content-Length": str(len(encrypted_message)),
        },
    )
    return encrypted_message, headers


def decrypt_response_content(context: spnego.ContextProxy, content: bytes, content_type: str) -> bytes:
    if f'protocol="{PROTOCOL}"' in content_type:
        return _decrypt_response(context, content)
    return content


__all__ = ["encrypt_message", "decrypt_response_content", "SOAP_CONTENT_TYPE"]
