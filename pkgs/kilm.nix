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

  runtimeDependencies = map requirementName project.dependencies;
in
python3Packages.buildPythonPackage {
  pname = project.name;
  inherit (project) version;
  pyproject = true;

  inherit src;

  build-system = [ python3Packages.hatchling ];

  dependencies = map (name: python3Packages.${name}) runtimeDependencies;

  # `kilm sync` and `kilm add-hook` shell out to git. Append it to the wrapper's
  # PATH so it is always available, while a git already on the user's PATH (and
  # its credential helpers) keeps precedence.
  makeWrapperArgs = [
    "--suffix"
    "PATH"
    ":"
    (lib.makeBinPath [ git ])
  ];

  nativeCheckInputs = [
    git
    python3Packages.pytestCheckHook
  ];

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
