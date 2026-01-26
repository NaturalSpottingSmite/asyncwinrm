{
  buildPythonPackage,
  uv-build,

  lxml,
  pyspnego,
  yarl,
  httpx,
  gssapi,
  krb5,

  # check phase
  ruff,
  ty,

  withNtlm ? false,
  httpx-ntlm-fixed,

  withKerberos ? false,
  httpx-gssapi,

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
    lxml
    pyspnego
    yarl
    httpx
  ]
  ++ lib.optional withNtlm httpx-ntlm-fixed
  ++ lib.optionals withKerberos [
    httpx-gssapi
    gssapi
    krb5
  ];

  nativeCheckInputs = [
    ruff
    ty
  ];

  checkPhase = ''
    runHook preCheck
    ruff check
    ty check --extra-search-path ./src
    runHook postCheck
  '';

  meta.mainProgram = "audit-forwarder";
}
