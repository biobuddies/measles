"""Continuous cookiecutter featuring mise."""

from base64 import b64decode
from collections import defaultdict
from json import load
from os import environ, getenv
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
    cona = getenv('CONA', '')
    if not cona and (repository_from_environment := getenv('GITHUB_REPOSITORY')):
        cona = repository_from_environment.split('/')[-1]
    if not cona and (Path.cwd() / '.git').exists():
        try:
            remote = check_output(['git', 'remote', 'get-url', 'origin']).decode().strip()
            if repository_from_remote := search(r'github.com[:/][^/]+/([^/]+)', remote):
                cona = repository_from_remote.group(1).removesuffix('.git')
        except CalledProcessError:
            pass
    if not cona and (virtual_environment := getenv('VIRTUAL_ENV')):
        cona = Path(virtual_environment).parent.name
    cona = cona or Path.cwd().name
    if fullmatch(r'[A-Za-z0-9._-]+', cona):
        return cona
    raise ValueError(f'Unexpected CONA characters: {cona!r}')


def orgn() -> str:
    """ORGanizatioN, a four-letter abbreviation."""
    if orgn := getenv('ORGN'):
        pass
    elif repository_owner := getenv('GITHUB_REPOSITORY_OWNER'):
        orgn = repository_owner
    else:
        if not (Path.cwd() / '.git').exists():
            return 'github-organization-unknown'
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
    gitignore_path = Path(environ['PWD']) / '.gitignore'
    existing = gitignore_path.read_text().splitlines() if gitignore_path.exists() else []
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
        # Cookiecutter renders output paths through from_string (generate.py) but also multi-line
        # hook bodies (hooks.py); strip the .j2 marker from single-line paths only, so
        # pyproject.j2.toml renders to pyproject.toml while linters treat sources as Jinja
        render = environment.from_string
        environment.from_string = lambda source, *arguments, **keywords: render(
            # pyrefly: ignore[missing-attribute,not-iterable]
            source.replace('.j2', '') if '\n' not in source else source,
            *arguments,
            **keywords,
        )
        # $PWD survives cookiecutter's os.chdir() to the template repo during
        # run_hook_from_repo_dir(). Path.cwd() would find the wrong .cookiecutter.yaml
        yaml_path = Path(environ['PWD']) / '.cookiecutter.yaml'
        default_context = defaultdict(dict, safe_load(yaml_path.read_text())['default_context'])

        # pyrefly: ignore[no-matching-overload,unsupported-operation]
        environment.globals.update({
            'CONA': cona(),
            'ORGN': orgn(),
            'classifiers': default_context.get('classifiers', []),
            'gitignore': gitignore,
            'python_dependencies': default_context.get('python_dependencies', []),
            'node_dependencies': default_context['node_dependencies'],
            'node_dev_dependencies': default_context['node_dev_dependencies'],
            'python_optional_dependencies': default_context['python_optional_dependencies'],
        })
        # pyrefly: ignore[not-iterable,unsupported-operation]
        environment.globals['has_django'] = any(
            'django' in dependency.lower()
            # pyrefly: ignore[not-iterable]
            for dependency in environment.globals['python_dependencies']
        )
        # pyrefly: ignore[unsupported-operation]
        environment.globals['python_test_dependencies'] = [
            'pytest',
            'pytest-cov',
            *(('pytest-django',) if environment.globals['has_django'] else ()),
        ]
