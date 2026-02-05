{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { nixpkgs, self, ... }: let
    forEachSystem = f: nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (s: f nixpkgs.legacyPackages.${s});
    pythonOverlay = final: prev: {
      asyncwinrm = final.callPackage ./. { };
    };
  in {
    overlays = {
      default = self.overlays.asyncwinrm;
      asyncwinrm = final: prev: {
        python313 = prev.python313.override {
          packageOverrides = pythonOverlay;
        };
        python314 = prev.python314.override {
          packageOverrides = pythonOverlay;
        };
        python3 = prev.python3.override {
          packageOverrides = pythonOverlay;
        };
      };
    };

    packages = forEachSystem (pkgs: rec {
      default = asyncwinrm;
      inherit ((self.overlays.default pkgs pkgs).python3.pkgs) asyncwinrm;
    });

    checks = forEachSystem (pkgs: rec {
      inherit ((self.overlays.default pkgs pkgs).python3.pkgs) asyncwinrm;
    });
  };
}
