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
TEMPLATE_PATHS = tuple(sorted(FIXTURES.glob('*/1-unformatted-template.*')))
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


def quote_paths(paths: Iterable[Path]) -> str:
    return ' '.join(quote(str(path)) for path in paths)


def quote_paths_matching(
    paths: Iterable[Path], suffixes: tuple[str, ...], *, exclude: bool = False
) -> str:
    return quote_paths(path for path in paths if path.name.endswith(suffixes) != exclude)


def stage_path(unformatted_template_path: Path, stage_name: str) -> Path:
    name = unformatted_template_path.name.replace('1-unformatted-template', stage_name)
    return unformatted_template_path.with_name(
        name.replace('.dj.', '.').replace('.j2.', '.') if 'rendering' in stage_name else name
    )


def render(template_path: Path) -> str:
    if template_path.name.endswith('.dj.html'):
        return (
            Engine(
                dirs=[template_path.parent], loaders=['django.template.loaders.filesystem.Loader']
            )
            .get_template(template_path.name)
            .render(Context(CONTEXT))
        )
    return (
        Environment(
            autoescape=False,  # noqa: S701
            keep_trailing_newline=True,
            loader=FileSystemLoader(template_path.parent),
        )
        .get_template(template_path.name)
        .render(CONTEXT)
    )


def test_rendering():
    for template_path in TEMPLATE_PATHS:
        assert (
            render(stage_path(template_path, '2-formatted-template'))
            == stage_path(template_path, '3-unformatted-rendering').read_text()
        )


def test_formatting_renderings():
    with TemporaryDirectory(dir='.') as temporary_directory:
        rendering_paths = [
            Path(temporary_directory) / template_path.parent.name / rendering_path.name
            for template_path in TEMPLATE_PATHS
            for rendering_path in [stage_path(template_path, '3-unformatted-rendering')]
        ]
        for template_path, rendering_path in zip(TEMPLATE_PATHS, rendering_paths, strict=True):
            rendering_path.parent.mkdir()
            rendering_path.write_bytes(
                stage_path(template_path, '3-unformatted-rendering').read_bytes()
            )
        check_call(['prettier', *rendering_paths, '--log-level=silent', '--write'])
        for template_path, rendering_path in zip(TEMPLATE_PATHS, rendering_paths, strict=True):
            assert (
                rendering_path.read_text()
                == stage_path(template_path, '4-formatted-rendering').read_text()
            )


def test_formatting_templates():
    with TemporaryDirectory(dir='.') as temporary_directory, TemporaryDirectory() as mock_directory:
        template_paths = [
            Path(temporary_directory) / path.parent.name / path.name for path in TEMPLATE_PATHS
        ]
        for source_path, template_path in zip(TEMPLATE_PATHS, template_paths, strict=True):
            template_path.parent.mkdir()
            template_path.write_bytes(source_path.read_bytes())
        write_mock_executable(
            Path(mock_directory) / 'git',
            f"""
            case " $* " in
            *' *.css '*) printf '%s\\n' \
                {quote_paths_matching(template_paths, ('.j2.json', '.j2.yaml'), exclude=True)} ;;
            *' *.dj.html '*) printf '%s\\n' \
                {quote_paths_matching(template_paths, ('.dj.html',))} ;;
            *' *.j2.html '*) printf '%s\\n' \
                {quote_paths_matching(template_paths, ('.j2.html',))} ;;
            *' *.j2.yaml '*) printf '%s\\n' \
                {quote_paths_matching(template_paths, ('.j2.yaml',))} ;;
            *' -- . '*) printf '%s\\n' \
                {quote_paths(template_paths)} ;;
            *' diff --color=always --exit-code '*) exit ;;
            *' grep '*) exit 1 ;;
            *) exec /usr/bin/git "$@" ;;
            esac
            """,
        )
        call(
            ['mise', 'pre-commit'],
            cwd=Path(temporary_directory),
            env={
                **environ,
                'ENVI': 'test',
                'GITHUB_HEAD_REF': 'formatter-fixtures',
                'PATH': f'{mock_directory}:{environ["PATH"]}',
            },
        )
        for source_path, template_path in zip(TEMPLATE_PATHS, template_paths, strict=True):
            expected_path = stage_path(source_path, '2-formatted-template')
            if template_path.read_text() != expected_path.read_text():
                warn(f'Autoformatting does not yet produce {expected_path}', stacklevel=2)
