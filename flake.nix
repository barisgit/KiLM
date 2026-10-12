{
  # Pins nixpkgs and wires outputs; build logic lives in pkgs/kilm.nix.
  description = "KiLM (KiCad Library Manager)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    let
      # nixpkgs-unstable no longer evaluates packages for x86_64-darwin.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      perSystem =
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          kilm = pkgs.callPackage ./pkgs/kilm.nix { src = self; };
        in
        {
          packages.kilm = kilm;
          packages.default = kilm;

          # `nix run github:barisgit/KiLM` and `nix run .#kilm`.
          apps.kilm = flake-utils.lib.mkApp { drv = kilm; };
          apps.default = flake-utils.lib.mkApp { drv = kilm; };

          # `nix flake check` builds the package, which runs the test suite.
          checks.kilm = kilm;

          devShells.default = pkgs.mkShell {
            # Python, runtime deps, and pytest come from the package. Lint and
            # type-check through `uv run` so ruff and pyrefly match uv.lock.
            inputsFrom = [ kilm ];
            packages = [ pkgs.uv ];
            # Import the in-tree package instead of requiring an install step.
            shellHook = ''
              export PYTHONPATH="$PWD''${PYTHONPATH:+:$PYTHONPATH}"
            '';
          };
        };
    in
    flake-utils.lib.eachSystem systems perSystem
    // {
      overlays.default = final: _prev: {
        kilm = final.callPackage ./pkgs/kilm.nix { src = self; };
      };
    };
}
