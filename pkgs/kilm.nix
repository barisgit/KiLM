{
  # Build logic for kilm (KiCad Library Manager). buildPythonPackage, hatchling backend.
  # Invoked via callPackage; `src` is overridden by the flake overlay.
  python3Packages,
  git,
}:

python3Packages.buildPythonPackage {
  pname = "kilm";
  version = "0.5.5";
  pyproject = true;

  src = null; # flake overrides via overrideAttrs

  build-system = with python3Packages; [ hatchling ];

  # `pathlib` is declared in pyproject but is stdlib; the PyPI backport is a
  # no-op and absent from nixpkgs, so drop the requirement.
  pythonRemoveDeps = [ "pathlib" ];

  # Runtime deps from pyproject. `pathlib` dep dropped: stdlib since py3, the PyPI
  # backport is a no-op on a modern interpreter.
  dependencies = with python3Packages; [
    click
    typer
    rich
    packaging
    pyyaml
    pathspec
    jinja2
    questionary
    requests
  ];

  nativeCheckInputs = [ git ] ++ (with python3Packages; [ pytest-cov pytestCheckHook ]);

  # Tests shell out to `git` and write into HOME; give them a writable one.
  preCheck = ''
    export HOME=$TMPDIR
  '';

  meta = {
    description = "Command-line tool for managing KiCad libraries across projects and workstations";
    mainProgram = "kilm";
  };
}
