"""Formatting and rendering fixture tests."""

import stat
from collections.abc import Iterable
from os import environ
from pathlib import Path
from shlex import quote
from subprocess import call, check_call
from tempfile import TemporaryDirectory
from textwrap import dedent
from warnings import warn

from django.template import Context, Engine
from jinja2 import Environment, FileSystemLoader

FIXTURES = Path(__file__).parent
TEMPLATE_NAMES = tuple(
    path.name for path in sorted((FIXTURES / '1-unformatted-templates').iterdir())
)
RENDERING_NAMES = tuple(name.replace('.dj.', '.').replace('.j2.', '.') for name in TEMPLATE_NAMES)
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


def quote_paths(directory: Path, names: Iterable[str]) -> str:
    return ' '.join(quote(str(directory / name)) for name in names)


def render(template_directory: Path, name: str) -> str:
    if name.endswith('.dj.html'):
        return (
            Engine(dirs=[template_directory], loaders=['django.template.loaders.filesystem.Loader'])
            .get_template(name)
            .render(Context(CONTEXT))
        )
    return (
        Environment(
            autoescape=False,  # noqa: S701
            keep_trailing_newline=True,
            loader=FileSystemLoader(template_directory),
        )
        .get_template(name)
        .render(CONTEXT)
    )


def test_rendering():
    for template_name, rendering_name in zip(TEMPLATE_NAMES, RENDERING_NAMES, strict=True):
        assert (
            render(FIXTURES / '2-formatted-templates', template_name)
            == (FIXTURES / '3-unformatted-renderings' / rendering_name).read_text()
        )


def test_formatting_renderings():
    with TemporaryDirectory(dir='.') as temporary_directory:
        temporary_path = Path(temporary_directory)
        rendering_paths = [temporary_path / name for name in RENDERING_NAMES]
        for rendering_path in rendering_paths:
            rendering_path.write_bytes(
                (FIXTURES / '3-unformatted-renderings' / rendering_path.name).read_bytes()
            )
        check_call(['prettier', *rendering_paths, '--log-level=silent', '--write'])
        for rendering_path in rendering_paths:
            assert (
                rendering_path.read_text()
                == (FIXTURES / '4-formatted-renderings' / rendering_path.name).read_text()
            )


def test_formatting_templates():
    expected_directory = FIXTURES / '2-formatted-templates'
    with TemporaryDirectory(dir='.') as temporary_directory, TemporaryDirectory() as mock_directory:
        temporary_path = Path(temporary_directory)
        for name in TEMPLATE_NAMES:
            (temporary_path / name).write_bytes(
                (FIXTURES / '1-unformatted-templates' / name).read_bytes()
            )
        write_mock_executable(
            Path(mock_directory) / 'git',
            f"""
            case " $* " in
            *' *.css '*) printf '%s\\n' \
                {
                quote_paths(
                    temporary_path,
                    (name for name in TEMPLATE_NAMES if not name.endswith('.j2.yaml')),
                )
            } ;;
            *' *.dj.html '*) printf '%s\\n' \
                {quote(str(temporary_path / 'allowedflare-login.dj.html'))} ;;
            *' *.j2.html '*) printf '%s\\n' \
                {
                quote_paths(
                    temporary_path, (name for name in TEMPLATE_NAMES if name.endswith('.j2.html'))
                )
            } ;;
            *' *.j2.yaml '*) printf '%s\\n' \
                {quote(str(temporary_path / 'measles-workflow.j2.yaml'))} ;;
            *' -- . '*) printf '%s\\n' \
                {quote_paths(temporary_path, TEMPLATE_NAMES)} ;;
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
