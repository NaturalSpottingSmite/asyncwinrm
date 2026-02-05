{
  buildPythonPackage,
  uv-build,

  isodate,
  lxml,
  pyspnego,
  yarl,
  httpx,

  # check phase
  ruff,
  ty,
  types-lxml,

  withKerberos ? false,
  gssapi,
  krb5,

  lib,
}:

let
  inherit (builtins.fromTOML (builtins.readFile ./pyproject.toml)) project;
in

buildPythonPackage {
  pname = project.name;
  inherit (project) version;
  pyproject = true;

  src = ./.;

  build-system = [ uv-build ];

  dependencies = [
    isodate
    lxml
    pyspnego
    yarl
    httpx
  ]
  ++ lib.optionals withKerberos [
    gssapi
    krb5
  ];

  nativeCheckInputs = [
    ruff
    ty
    types-lxml
  ];

  checkPhase = ''
    runHook preCheck
    ruff check
    ty check --extra-search-path ./src
    runHook postCheck
  '';

  meta = {
    description = "Asynchronous WinRM library for Python";
    license = lib.licenses.mit;
  };
}
