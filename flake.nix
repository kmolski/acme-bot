{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
  };
  outputs = { nixpkgs, ... }:
    let
      forAllSystems = f: nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (
        system: f { pkgs = import nixpkgs { inherit system; }; }
      );
    in
    {
      devShells = forAllSystems
        ({ pkgs }: {
          default = with pkgs; mkShell {
            buildInputs = [
              (python313.withPackages (ps: with ps; [ ruff poetry-dynamic-versioning ]))
              basedpyright
              poetry
            ];
          };
        });
    };
}
