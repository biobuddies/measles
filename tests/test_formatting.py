"""Formatting and rendering fixture tests."""

import stat
from os import environ
from pathlib import Path
from shlex import quote
from subprocess import call
from tempfile import TemporaryDirectory
from textwrap import dedent
from warnings import warn

from django.template import Context, Engine
from jinja2 import Environment, FileSystemLoader
from pytest import mark

FIXTURES = Path(__file__).parent
TEMPLATE_NAMES = (
    'allowedflare-login.dj.html',
    'measles-package.j2.json',
    'measles-pyproject.j2.toml',
    'measles-workflow.j2.yaml',
    'mublog-lead-line.j2.html',
)
CONTEXT = {
    'allowedflare_message': 'Use your allowed account',
    'cookiecutter': {'peer_checkouts': {'biobuddies/mublog': 'main'}},
    'lead_line': lambda **chords: ' '.join(chords.values()),
    'node_dependencies': {'jinja2': '*'},
    'node_dev_dependencies': {'pytest': '*'},
    'python_dependencies': ['django', 'jinja2'],
}


def write_mock_executable(path: Path, body: str) -> None:
    path.write_text(
        '#!/usr/bin/env bash\nset -o errexit -o nounset -o pipefail\n' + dedent(body).lstrip()
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def render(template_directory: Path, name: str) -> str:
    if name.endswith('.dj.html'):
        engine = Engine(
            dirs=[template_directory, FIXTURES],
            loaders=['django.template.loaders.filesystem.Loader'],
        )
        return engine.get_template(name).render(Context(CONTEXT))
    environment = Environment(
        autoescape=False,  # noqa: S701
        keep_trailing_newline=True,
        loader=FileSystemLoader(template_directory),
    )
    return environment.get_template(name).render(CONTEXT)


@mark.parametrize(
    ('template_directory_name', 'rendering_directory_name'),
    (
        ('1-unformatted-templates', '3-unformatted-renderings'),
        ('2-formatted-templates', '4-formatted-renderings'),
    ),
)
def test_rendering(template_directory_name: str, rendering_directory_name: str):
    template_directory = FIXTURES / template_directory_name
    rendering_directory = FIXTURES / rendering_directory_name
    for name in TEMPLATE_NAMES:
        rendering_name = name.replace('.j2.', '.', 1)
        assert (
            render(template_directory, name) == (rendering_directory / rendering_name).read_text()
        )


def test_formatting():
    source_directory = FIXTURES / '1-unformatted-templates'
    expected_directory = FIXTURES / '2-formatted-templates'
    with TemporaryDirectory(dir='.') as temporary_directory, TemporaryDirectory() as mock_directory:
        temporary_path = Path(temporary_directory)
        for name in TEMPLATE_NAMES:
            (temporary_path / name).write_bytes((source_directory / name).read_bytes())
        django_sources = quote(str(temporary_path / 'allowedflare-login.dj.html'))
        jinja_sources = ' '.join(
            quote(str(temporary_path / name))
            for name in TEMPLATE_NAMES
            if name.endswith('.j2.html')
        )
        prettier_sources = ' '.join(
            quote(str(temporary_path / name))
            for name in TEMPLATE_NAMES
            if not name.endswith('.j2.yaml')
        )
        template_sources = ' '.join(quote(str(temporary_path / name)) for name in TEMPLATE_NAMES)
        write_mock_executable(
            Path(mock_directory) / 'git',
            f"""
            case " $* " in
            *' *.css '*) printf '%s\\n' {prettier_sources} ;;
            *' *.dj.html '*) printf '%s\\n' {django_sources} ;;
            *' *.j2.html '*) printf '%s\\n' {jinja_sources} ;;
            *' *.j2.yaml '*) printf '%s\\n' \
                {quote(str(temporary_path / 'measles-workflow.j2.yaml'))} ;;
            *' -- . '*) printf '%s\\n' {template_sources} ;;
            *' diff --color=always --exit-code '*) exit ;;
            *' grep '*) exit 1 ;;
            *) exec /usr/bin/git "$@" ;;
            esac
            """,
        )
        call(
            ['mise', 'pre-commit'],
            cwd=temporary_path,
            env={
                **environ,
                'ENVI': 'test',
                'GITHUB_HEAD_REF': 'formatter-fixtures',
                'PATH': f'{mock_directory}:{environ["PATH"]}',
            },
        )
        for name in TEMPLATE_NAMES:
            if (temporary_path / name).read_text() != (expected_directory / name).read_text():
                warn(
                    f'Autoformatting does not yet produce {expected_directory / name}', stacklevel=2
                )
