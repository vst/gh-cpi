{
  description = "Create GitHub Project Issues";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/release-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        pythonDev = pkgs.python3.withPackages (ps: [
          ## Production Dependencies:
          ps.dateutil
          ps.pydantic
          ps.python-frontmatter

          ## Testing tools:
          ps.mypy
          ps.black
          ps.isort
          ps.flake8

          ## Python Language Server:
          ps.python-lsp-server

          ## Python Language Server Plugins:
          ps.pyls-flake8
          ps.pyls-isort
          ps.pylsp-mypy
          ps.python-lsp-black
        ]);
      in
      {
        packages = {
          default = pkgs.writers.writePython3Bin "gh-cpi"
            {
              doCheck = false;
              libraries = [
                pkgs.python3Packages.dateutil
                pkgs.python3Packages.pydantic
                pkgs.python3Packages.python-frontmatter
              ];
            }
            (builtins.readFile ./gh-cpi.py);
        };
        devShell = pkgs.mkShell {
          buildInputs = [
            pythonDev
          ];
        };
      }
    );
}
