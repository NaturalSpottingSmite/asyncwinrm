from gssapi import Name, Credentials, NameType
from gssapi.raw.ext_password import acquire_cred_with_password
from httpx import Auth
from httpx_gssapi import HTTPSPNEGOAuth, REQUIRED


def kerberos(username: str, password: str, *, realm: str) -> Auth:
    """
    Creates a new Kerberos auth handler.

    :param username: The username to use.
    :param password: The password to use.
    :param realm: The realm/domain to use.
    """
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


__all__ = ["kerberos"]
