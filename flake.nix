{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { nixpkgs, self, ... }: let
    forEachSystem = f: nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (s: f nixpkgs.legacyPackages.${s});
  in {
    overlays = {
      default = self.overlays.asyncwinrm;
      asyncwinrm = final: prev: {
        python3 = prev.python3.override {
          packageOverrides = final: prev: {
            httpx-ntlm-fixed = final.callPackage ./nix/httpx-ntlm-fixed.nix { };
            httpx-gssapi = final.callPackage ./nix/httpx-gssapi.nix { };
            asyncwinrm = final.callPackage ./. { };
          };
        };
      };
    };

    packages = forEachSystem (pkgs: rec {
      default = asyncwinrm;
      inherit ((self.overlays.default pkgs pkgs).python3.pkgs) asyncwinrm;
    });
  };
}
