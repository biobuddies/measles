"""Test the Measles Cookiecutter extension."""

from collections.abc import Callable
from os import environ
from pathlib import Path

from jinja2 import Environment
from pytest import MonkeyPatch, fixture, raises

import measles

MISSING = object()


@fixture
def precise_environment(monkeypatch: MonkeyPatch) -> Callable[..., None]:
    def set_environment(**environment: str) -> None:
        for key, value in (
            dict.fromkeys(
                (
                    'CONA',
                    'GITHUB_REPOSITORY',
                    'GITHUB_REPOSITORY_OWNER',
                    'ORGN',
                    'PWD',
                    'VIRTUAL_ENV',
                ),
                MISSING,
            )
            | environment
        ).items():
            if value is MISSING:
                monkeypatch.delitem(environ, key, raising=False)
            else:
                monkeypatch.setenv(key, value)  # pyrefly: ignore[bad-argument-type]

    return set_environment


def test_cona_eponymous(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(
        CONA='measles',
        GITHUB_REPOSITORY='ton/wriggle',
        VIRTUAL_ENV=str(tmp_path / 'wriggle' / '.venv'),
    )

    assert measles.cona() == 'measles'


def test_cona_uses_github_repository(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(GITHUB_REPOSITORY='biobuddies/measles')

    assert measles.cona() == 'measles'


def test_cona_uses_git_remote(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    repository = tmp_path / 'repo'
    repository.mkdir()
    (repository / '.git').mkdir()
    monkeypatch.chdir(repository)
    precise_environment()
    monkeypatch.setattr(
        measles, 'check_output', lambda _: b'https://github.com/biobuddies/wriggle.git\n'
    )

    assert measles.cona() == 'wriggle'


def test_cona_uses_git_remote_in_worktree(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    repository = tmp_path / 'repo'
    repository.mkdir()
    (repository / '.git').write_text('gitdir: /tmp/main/.git/worktrees/repo\n')
    monkeypatch.chdir(repository)
    precise_environment()
    monkeypatch.setattr(
        measles, 'check_output', lambda _: b'git@github.com:biobuddies/wriggle.git\n'
    )

    assert measles.cona() == 'wriggle'


def test_cona_virtual_env(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(VIRTUAL_ENV=str(tmp_path / 'measles' / '.venv'))

    assert not (tmp_path / '.git').exists()
    assert measles.cona() == 'measles'


def test_cona_current_working_directory(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    current_working_directory = tmp_path / 'wriggle'
    current_working_directory.mkdir()
    monkeypatch.chdir(current_working_directory)
    precise_environment()

    assert measles.cona() == 'wriggle'


def test_cona_rejects_bad_characters(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(CONA='bad name')

    with raises(ValueError, match=r"^Unexpected CONA characters: 'bad name'$"):
        measles.cona()


def test_orgn_eponymous(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(GITHUB_REPOSITORY_OWNER='ton', ORGN='biobuddies')

    assert measles.orgn() == 'biobuddies'


def test_orgn_github_repository_owner(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(GITHUB_REPOSITORY_OWNER='biobuddies')

    assert measles.orgn() == 'biobuddies'


def test_orgn_uses_git_remote(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    repository = tmp_path / 'repo'
    repository.mkdir()
    (repository / '.git').mkdir()
    monkeypatch.chdir(repository)
    precise_environment()
    monkeypatch.setattr(
        measles, 'check_output', lambda _: b'git@github.com:biobuddies/wriggle.git\n'
    )

    assert measles.orgn() == 'biobuddies'


def test_orgn_unknown(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment()

    assert measles.orgn() == 'github-organization-unknown'


def test_orgn_rejects_bad_characters(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    monkeypatch.chdir(tmp_path)
    precise_environment(ORGN='bad name')

    with raises(ValueError, match=r"^Unexpected ORGN characters: 'bad name'$"):
        measles.orgn()


def test_from_string_strips_j2_from_paths(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    (tmp_path / '.cookiecutter.yaml').write_text('default_context: {}\n')
    monkeypatch.chdir(tmp_path)
    precise_environment(CONA='wriggle', ORGN='biobuddies', PWD=str(tmp_path))
    environment = Environment(autoescape=True, extensions=[measles.Measles])

    assert environment.from_string('sub/pyproject.j2.toml').render() == 'sub/pyproject.toml'
    # Multi-line hook bodies keep any .j2 they mention
    assert environment.from_string('name: {{ x }}\n.j2 stays').render(x='v') == 'name: v\n.j2 stays'
