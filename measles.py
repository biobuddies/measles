from os import getenv
from pathlib import Path
from subprocess import DEVNULL, check_output

from jinja2 import Environment
from jinja2.ext import Extension


class CodeNameExtension(Extension):
    """Inject CONA (COde NAme) into the Jinja environment."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        # pyrefly: ignore[unsupported-operation]
        environment.globals['CONA'] = self.discover_code_name()

    def discover_code_name(self) -> str:
        # TODO: single source of truth between mise and cookiecutter for codename lookup
        try:
            return check_output(['mise', 'cona'], stderr=DEVNULL, text=True).strip()
        except Exception:
            if repository := getenv('GITHUB_REPOSITORY'):
                return Path(repository).name
            if virtual_environment := getenv('VIRTUAL_ENV'):
                return Path(virtual_environment).parent.name
            return Path.cwd().name
