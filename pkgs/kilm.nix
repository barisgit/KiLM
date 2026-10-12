# Build recipe for kilm, invoked through callPackage with `src` set to the
# repository. Name, version, description, and runtime dependencies are read
# from pyproject.toml so the Nix package cannot drift from the Python metadata.
{
  lib,
  python3Packages,
  git,
  src,
}:

let
  project = (lib.importTOML (src + "/pyproject.toml")).project;

  # Requirement strings look like "typer>=0.17.4"; keep the distribution name,
  # which matches the nixpkgs attribute for every current dependency.
  requirementName =
    requirement: lib.toLower (builtins.head (builtins.match "([A-Za-z0-9._-]+).*" requirement));

  # `pathlib` is declared in pyproject but is stdlib on Python 3; the PyPI
  # backport is a no-op and absent from nixpkgs.
  stdlibBackports = [ "pathlib" ];

  runtimeDependencies = lib.subtractLists stdlibBackports (map requirementName project.dependencies);
in
python3Packages.buildPythonPackage {
  pname = project.name;
  inherit (project) version;
  pyproject = true;

  inherit src;

  build-system = [ python3Packages.hatchling ];

  pythonRemoveDeps = stdlibBackports;

  dependencies = map (name: python3Packages.${name}) runtimeDependencies;

  # pytest-cov is required because pyproject's pytest addopts pass --cov.
  nativeCheckInputs = [
    git
  ]
  ++ (with python3Packages; [
    pytest-cov
    pytestCheckHook
  ]);

  # Tests shell out to `git` and write into HOME; give them a writable one.
  preCheck = ''
    export HOME=$TMPDIR
  '';

  meta = {
    inherit (project) description;
    homepage = project.urls.Homepage;
    license = lib.licenses.mit;
    mainProgram = "kilm";
  };
}
