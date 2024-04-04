{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  buildInputs = with pkgs; [
    python311Full
    poetry
  ];
  shellHook = "exec poetry shell";
}
