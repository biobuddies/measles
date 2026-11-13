"""Continuous cookiecutter featuring mise."""

from collections import defaultdict
from hashlib import sha1
from itertools import takewhile
from os import environ, getenv
from pathlib import Path
from re import fullmatch, search
from subprocess import DEVNULL, CalledProcessError, call, check_output, run
from sys import stderr
from textwrap import dedent
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from cookiecutter import hooks
from cookiecutter.hooks import valid_hook
from jinja2 import Environment, Template
from jinja2.ext import Extension
from yaml import safe_load

# $PWD survives cookiecutter's os.chdir() to the template repo during
# run_hook_from_repo_dir(). Path.cwd() would find the wrong .cookiecutter.yaml
PWD = Path(environ['PWD'])


def cona() -> str:
    """COde NAme, a four-letter abbreviation."""
    cona = getenv('CONA', '')
    if not cona and (repository_from_environment := getenv('GITHUB_REPOSITORY')):
        cona = repository_from_environment.split('/')[-1]
    if not cona and (PWD / '.git').exists():
        try:
            remote = check_output(['git', 'remote', 'get-url', 'origin'], cwd=PWD).decode().strip()
            if repository_from_remote := search(r'github.com[:/][^/]+/([^/]+)', remote):
                cona = repository_from_remote.group(1).removesuffix('.git')
        except CalledProcessError:
            pass
    if not cona and (virtual_environment := getenv('VIRTUAL_ENV')):
        cona = Path(virtual_environment).parent.name
    cona = cona or PWD.resolve().name
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
        if not (PWD / '.git').exists():
            return 'github-organization-unknown'
        try:
            remote = check_output(['git', 'remote', 'get-url', 'origin'], cwd=PWD).decode().strip()
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
    gitignore_path = PWD / '.gitignore'
    existing = gitignore_path.read_text().splitlines()[2:] if gitignore_path.exists() else []
    hashes = [*takewhile(lambda line: fullmatch(r'# [\w+-]+=[0-9a-f]+', line), existing)]
    body = '\n'.join(existing[len(hashes) :]) + '\n'
    try:
        upstream = [
            urlopen(
                f'https://raw.githubusercontent.com/github/gitignore/main/{name}.gitignore'
            ).read()
            for name in names
        ]
    except HTTPError as error:
        if error.code not in {403, 429}:
            raise
        stderr.write(
            'Warning: skipping .gitignore update after GitHub fetch failed: '
            f'HTTP {error.code} {error.reason}\n'
        )
    except URLError:
        stderr.write('Warning: skipping .gitignore update after GitHub fetch failed: URL error\n')
    else:
        body = b''.join(upstream).decode()
        hashes = [
            f'# {name}='
            + sha1(b'blob %d\0' % len(content) + content, usedforsecurity=False).hexdigest()
            for name, content in zip(names, upstream, strict=True)
        ]
    if Path('.gitignore.sed').exists():
        # short flags for Darwin compatibility
        body = check_output(['sed', '-E', '-f', '.gitignore.sed'], input=body.encode()).decode()
    return '\n'.join((*hashes, body))


# Hash Jinja (.hj.) templates hide tags in # comments, staying valid YAML for prettier
hash_jinja: dict[str, Any] = {
    'block_end_string': '%#',
    'block_start_string': '#%',
    'comment_end_string': '*#',
    'comment_start_string': '#*',
    'lstrip_blocks': True,
    'trim_blocks': True,
    'variable_end_string': '}#',
    'variable_start_string': '#{',
}


class Measles(Extension):
    """Set globals."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        # Cookiecutter renders output paths through from_string (generate.py) but also multi-line
        # hook bodies (hooks.py); strip the .hj and .j2 markers from single-line paths only, so
        # pyproject.j2.toml renders to pyproject.toml while linters treat sources as Jinja
        render = environment.from_string
        environment.from_string = lambda source, *args, **kwargs: render(
            # pyrefly: ignore[missing-attribute,not-iterable]
            source.replace('.hj', '').replace('.j2', '') if '\n' not in source else source,
            *args,
            **kwargs,
        )
        # Cookiecutter matches hook stems exactly; accept post_gen_project.j2.bash too
        hooks.valid_hook = lambda hook_file, hook_name: valid_hook(
            hook_file.replace('.j2', ''), hook_name
        )
        get_template = environment.get_template

        def get_hash_or_curly_template(name: str, *args: Any, **kwargs: Any) -> Template:
            if '.hj.' not in name:
                return get_template(name, *args, **kwargs)
            # Overlay late: extensions load after __init__, and cookiecutter sets loader later still
            return Environment.get_template(
                environment.overlay(**hash_jinja), name, *args, **kwargs
            )

        environment.get_template = get_hash_or_curly_template
        default_context = defaultdict(
            dict,
            safe_load(yaml_source := (PWD / '.cookiecutter.yaml').read_text())['default_context'],
        )
        github_actions_env = default_context.pop('github_actions_env', {})

        # pyrefly: ignore[no-matching-overload,unsupported-operation]
        environment.globals.update({
            'CONA': cona(),
            'ORGN': orgn(),
            'TABR': run(
                ['mise', 'tabr'], capture_output=True, check=False, cwd=PWD, text=True
            ).stdout.strip(),
            'classifiers': default_context.get('classifiers', []),
            'gitignore': gitignore,
            'github_actions_env': (
                dedent(match.group()).replace('github_actions_env:', 'env:', 1)
                if github_actions_env
                and (
                    match := search(r'(?ms)^    github_actions_env:.*?(?=^    \S|\Z)', yaml_source)
                )
                else ''
            ),
            'python_dependencies': sorted({
                *default_context.get('python_dependencies', []),
                *(['helicopyter'] if default_context.get('domain_name') else []),
            }),
            'node_dependencies': default_context['node_dependencies'],
            'node_dev_dependencies': default_context['node_dev_dependencies'],
            'python_optional_dependencies': default_context['python_optional_dependencies'],
        })
        # Help new repositories run the workflow
        environment.globals['branch_trigger'] = (
            # pyrefly: ignore[unsupported-operation]
            environment.globals['TABR'] not in ('', 'main')
            and call(
                ['git', 'cat-file', '-e', 'origin/main:.github/workflows/act.yaml'],
                cwd=PWD,
                stderr=DEVNULL,
            )
            != 0
        )
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
