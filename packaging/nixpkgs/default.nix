{
  lib,
  python3,
  fetchFromGitHub,
}:

python3.pkgs.buildPythonApplication rec {
  pname = "pimpmyrice";
  version = "0.3.2";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "daddodev";
    repo = "pimpmyrice";
    rev = version;
    hash = "sha256-AsuWeCSZt2Bz3ZMFtOPYNPZlppkUkfQ7wcitR9SZhd4=";
  };

  build-system = [
    python3.pkgs.setuptools
    python3.pkgs.wheel
  ];

  dependencies = [
    python3.pkgs.rich
    python3.pkgs.docopt
    python3.pkgs.pyyaml
    python3.pkgs.jinja2
    python3.pkgs.requests
    python3.pkgs.psutil
    python3.pkgs.numpy
    python3.pkgs.pillow
    python3.pkgs.pydantic
    python3.pkgs.typing-extensions
    # TO REMOVE
    python3.pkgs.scikit-learn
    python3.pkgs.opencv-python
    python3.pkgs.pydantic-extra-types
  ];

  pythonImportsCheck = [
    "pimpmyrice"
  ];

  meta = {
    description = "The overkill theme manager";
    homepage = "https://github.com/daddodev/pimpmyrice";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ ];
    mainProgram = "pimp";
  };
}
