"""Continuous cookiecutter featuring mise."""

from os import getenv
from pathlib import Path
from re import fullmatch, search
from subprocess import CalledProcessError, check_output

from jinja2 import Environment
from jinja2.ext import Extension
from yaml import safe_load


def cona() -> str:
    """COde NAme, a four-letter abbreviation."""
    if repository := getenv('GITHUB_REPOSITORY'):
        cona = repository.split('/')[-1]
    elif virtual_environment := getenv('VIRTUAL_ENV'):
        cona = Path(virtual_environment).parent.name
    else:
        cona = Path.cwd().name
    if fullmatch(r'[A-Za-z0-9._-]+', cona):
        return cona
    raise ValueError(f'Unexpected CONA characters: {cona!r}')


def orgn() -> str:
    """ORGanizatioN, a four-letter abbreviation."""
    if repository_owner := getenv('GITHUB_REPOSITORY_OWNER'):
        orgn = repository_owner
    else:
        try:
            remote = check_output(['git', 'remote', 'get-url', 'origin']).decode().strip()
        except CalledProcessError:
            return 'github-organization-unknown'
        if owner := search(r'github.com[:/]([^/]+)', remote):
            orgn = owner.group(1)
        else:
            raise ValueError(f'Unexpected origin URL: {remote!r}')
    if fullmatch(r'[A-Za-z0-9._-]+', orgn):
        return orgn
    raise ValueError(f'Unexpected ORGN characters: {orgn!r}')


class Measles(Extension):
    """Set globals."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        # pyrefly: ignore[no-matching-overload,unsupported-operation]
        environment.globals.update(
            {
                'CONA': cona(),
                'ORGN': orgn(),
                'python_dependencies': safe_load((Path.cwd() / '.cookiecutter.yaml').read_text())[
                    'default_context'
                ].get('python_dependencies', []),
            }
        )
