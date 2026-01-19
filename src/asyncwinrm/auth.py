from gssapi import Name, Credentials, NameType, MechType
from gssapi.raw.ext_password import acquire_cred_with_password
from httpx import Auth, BasicAuth
from httpx_gssapi import HTTPSPNEGOAuth, REQUIRED, SPNEGO
from httpx_ntlm import HttpNtlmAuth


def basic(username: str, password: str) -> Auth:
    """Basic auth"""
    return BasicAuth(username, password)


def ntlm(username: str, password: str) -> Auth:
    """NTLM auth"""
    return HttpNtlmAuth(username, password)


def kerberos(username: str, password: str, *, realm: str) -> Auth:
    """Kerberos auth"""
    # TODO: doesn't quite work yet
    principal = f"{username}@{realm}"
    name = Name(base=principal, name_type=NameType.kerberos_principal)
    res = acquire_cred_with_password(
        name,
        password.encode("utf-8"),
        # mechs=[SPNEGO],
    )
    credentials = Credentials(res.creds)
    return HTTPSPNEGOAuth(
        mutual_authentication=REQUIRED,
        target_name=Name(f"HTTP@{realm}", NameType.hostbased_service),
        opportunistic_auth=True,
        creds=credentials,
        sanitize_mutual_error_response=False,
    )
