{
  lib,
  buildPythonPackage,
  fetchPypi,
  httpx,
  pytestCheckHook,
  requests,
  setuptools,
}:

buildPythonPackage rec {
  pname = "httpx-gssapi";
  version = "0.6";
  pyproject = true;

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-TVK/jCqiqCkTDvzKhcFJQ/3QqnVFWquYWyuHJhWcIMo=";
  };

  build-system = [ setuptools ];

  dependencies = [
    httpx
    requests
  ];

  nativeCheckInputs = [ pytestCheckHook ];

  pythonImportsCheck = [ "httpx_gssapi" ];

  meta = {
    description = "GSSAPI authentication handler for httpx";
    homepage = "https://github.com/pythongssapi/httpx-gssapi";
    changelog = "https://github.com/pythongssapi/httpx-gssapi/blob/v${version}/HISTORY.rst";
    license = lib.licenses.isc;
#    maintainers = with lib.maintainers; [ javimerino ];
  };
}
