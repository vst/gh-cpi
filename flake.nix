{
  description = "Create GitHub Project Issues";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.05";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = inputs.nixpkgs.lib.systems.flakeExposed;
      perSystem = { pkgs, system, ... }:
        let
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

          pythonApp = pkgs.writers.writePython3Bin "gh-cpi"
            {
              doCheck = false;
              libraries = [
                pkgs.python3Packages.dateutil
                pkgs.python3Packages.pydantic
                pkgs.python3Packages.python-frontmatter
              ];
            }
            (builtins.readFile ./gh-cpi.py);
        in
        {
          packages.default = pythonApp;

          devShells.default = pkgs.mkShell {
            packages = [ pythonDev ];
          };
        };
    };
}
