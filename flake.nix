{
  description = "PimpMyRice: The overkill theme manager";

  inputs.pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
  inputs.pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";

  outputs =
    {
      nixpkgs,
      self,
      pyproject-nix,
      ...
    }:
    let
      project = pyproject-nix.lib.project.loadPyproject {
        projectRoot = ./.;
      };
      # TODO other archs
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      python = pkgs.python3;
    in
    {
      devShells.x86_64-linux.default =
        # let
        #   arg = project.renderers.withPackages { inherit python; };
        #   pythonEnv = python.withPackages arg;
        # in
        #   pkgs.mkShell { packages = [ pythonEnv ]; };
        pkgs.mkShell {
          buildInputs = with pkgs; [
            # Core Python
            python3
            # UV for package management
            uv
            # Development tools (still available for system use)
            ruff
            mypy
            isort
            python3Packages.python-lsp-server
            python3Packages.python-lsp-ruff
            python3Packages.pylsp-mypy
            python3Packages.pyls-isort
          ];

          shellHook = ''
            if [ ! -d ".git" ]; then
              echo "Please run this from the project root directory."
              exit 1
            fi

            if [ ! -d ".venv" ]; then
              echo "Creating virtual environment and installing dependencies with uv..."
              uv venv
              uv sync --dev

              echo "Installing in editable mode..."
              uv pip install -e .
            else
              echo "Virtual environment already set up. Syncing dependencies with uv..."
              uv sync --dev
            fi

            # Source the virtual environment
            source .venv/bin/activate
          '';
        };

      packages.x86_64-linux.pimpmyrice =
        let
          attrs = project.renderers.buildPythonPackage { inherit python; };
        in
        python.pkgs.buildPythonPackage (attrs);

      packages.x86_64-linux.default = self.packages.x86_64-linux.pimpmyrice;
    };
}
