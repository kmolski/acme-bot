{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  buildInputs = with pkgs; [
    (python311.withPackages (ps: with ps; [ poetry-dynamic-versioning ]))
    poetry
  ];
}
