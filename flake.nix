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
          buildInputs = with pkgs.python3Packages; [
            pkgs.python3
            pip
            build
            ruff
            mypy
            isort
            python-lsp-server
            pylsp-mypy
            pyls-isort
            pytest
            pytest-asyncio
            types-requests
            types-pyyaml
            numpy
            rich
            docopt
            pyyaml
            jinja2
            requests
            psutil
            pillow
            pydantic
            typing-extensions
          ];

          shellHook = ''
            if [ ! -d ".git" ]; then
              echo "Please run this from the project root directory."
              exit 1
            fi

            if [ ! -d ".venv" ]; then
              echo "Creating virtual environment and installing dependencies..."
              python3 -m venv .venv
              source .venv/bin/activate
              # pip install ~/development/iothingy
              # pip install homeassistant_api
              # pip install --editable ".[dev]"
              pip install --editable .
            else
              echo "Virtual environment already set up. Activating..."
              source .venv/bin/activate
            fi
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
