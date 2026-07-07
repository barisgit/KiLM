{
  # Pin nixpkgs, select dep versions, wire overlay, expose outputs.
  # NO build logic here — that lives in pkgs/kilm.nix.
  description = "Flake for kilm (KiCad Library Manager)";

  inputs = {
    nixpkgs.url = "https://github.com/NixOS/nixpkgs/archive/567a49d1913ce81ac6e9582e3553dd90a955875f.tar.gz";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    let
      out = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          applied = self.overlays.default pkgs pkgs;
        in {
          packages.kilm = applied.kilm;
          packages.default = applied.kilm;

          # `nix run github:barisgit/KiLM` and `nix run .#kilm`.
          apps.kilm = flake-utils.lib.mkApp { drv = applied.kilm; };
          apps.default = flake-utils.lib.mkApp { drv = applied.kilm; };

          devShells.default = pkgs.mkShell {
            inputsFrom = [ applied.kilm ];
            packages = with pkgs.python3Packages; [ pytest ruff ];
          };
        };
    in
      flake-utils.lib.eachDefaultSystem out // {
        overlays.default = final: prev:
          let
            python3Packages = prev.python3Packages;
          in {
            kilm =
              (prev.callPackage ./pkgs/kilm.nix {
                inherit python3Packages;
                inherit (prev) git;
              }).overrideAttrs (old: {
                # Local in-tree source.
                src = self;
              });
          };
      };
}
