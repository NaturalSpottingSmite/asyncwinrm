{
  httpx-ntlm,
  fetchPypi,
}:

httpx-ntlm.overrideAttrs (prev: rec {
  pname = "httpx-ntlm-fixed";
  version = "1.4.1";

  src = fetchPypi {
    inherit pname version;
    hash = "";
  };

  meta = prev.meta // {
    description = "NTLM authentication support for HTTPX. Fork of httpx-ntlm with fixes.";
    homepage = "https://github.com/LogicDaemon/httpx-ntlm";
    changelog = "https://github.com/LogicDaemon/httpx-ntlm/releases/tag/${version}";
  };
})
