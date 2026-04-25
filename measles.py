"""Continuous cookiecutter featuring mise."""

from base64 import b64decode
from json import load
from os import getenv
from pathlib import Path
from re import fullmatch, search
from subprocess import CalledProcessError, check_output
from sys import stderr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def gitignore(languages: str) -> str:
    names = languages.split(',')
    existing = (Path(__file__).parent / '.gitignore').read_text().splitlines()
    body_index = 3
    hashes = []
    while body_index < len(existing) and existing[body_index].startswith('# '):
        hashes.append(existing[body_index])
        body_index += 1
    try:
        upstream = [
            load(
                urlopen(
                    Request(
                        (f'https://api.github.com/repos/github/gitignore/contents/{path}?ref=main'),
                        headers=(
                            {'Authorization': f'Bearer {token}'}
                            if (token := getenv('GITHUB_TOKEN'))
                            else {}
                        ),
                    )
                )
            )
            for path in [f'{name}.gitignore' for name in names]
        ]
    except HTTPError as error:
        if error.code not in {403, 429}:
            raise
        stderr.write(
            'Warning: falling back to vendored .gitignore after GitHub fetch failed: '
            f'HTTP {error.code} {error.reason}\n'
        )
        body = '\n'.join(existing[body_index:]) + '\n'
    except URLError:
        stderr.write(
            'Warning: falling back to vendored .gitignore after GitHub fetch failed: URL error\n'
        )
        body = '\n'.join(existing[body_index:]) + '\n'
    else:
        body = ''.join(b64decode(item['content']).decode() for item in upstream)
        hashes = [f'# {name}={item["sha"]}' for name, item in zip(names, upstream, strict=True)]
    if Path('.gitignore.sed').exists():
        # short flags for Darwin compatibility
        body = check_output(['sed', '-E', '-f', '.gitignore.sed'], input=body.encode()).decode()
    return '\n'.join((*hashes, body))


class Measles(Extension):
    """Set globals."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        # pyrefly: ignore[no-matching-overload,unsupported-operation]
        environment.globals.update(
            {
                'CONA': cona(),
                'ORGN': orgn(),
                'gitignore': gitignore,
                'python_dependencies': safe_load((Path.cwd() / '.cookiecutter.yaml').read_text())[
                    'default_context'
                ].get('python_dependencies', []),
            }
        )
