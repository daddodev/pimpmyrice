{
  lib,
  python3,
  fetchFromGitHub,
}:

python3.pkgs.buildPythonApplication rec {
  # TODO gen from template
  pname = "pimpmyrice";
  version = "0.4.3";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "daddodev";
    repo = "pimpmyrice";
    rev = version;
    hash = "sha256-ANxDvoSNfJHjB4tJyelpQVaG7i2pqoYgXxkXU6oQWos=";
  };

  build-system = [
    python3.pkgs.setuptools
    python3.pkgs.wheel
  ];

  dependencies = with python3.pkgs; [
    rich
    docopt
    pyyaml
    jinja2
    requests
    psutil
    numpy
    pillow
    pydantic
    typing-extensions
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
