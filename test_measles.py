"""Test the Measles Cookiecutter extension."""

from os import environ
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from jinja2 import Environment
from pytest import raises

import measles


def clear_environment(monkeypatch: MonkeyPatch):
    for key in ('CONA', 'GITHUB_REPOSITORY', 'GITHUB_REPOSITORY_OWNER', 'ORGN', 'VIRTUAL_ENV'):
        monkeypatch.delitem(environ, key, raising=False)


def test_cona_eponymous(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    clear_environment(monkeypatch)
    monkeypatch.setenv('CONA', 'measles')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'ton/wriggle')
    monkeypatch.setenv('VIRTUAL_ENV', str(tmp_path / 'wriggle' / '.venv'))

    assert measles.cona() == 'measles'


def test_cona_uses_github_repository(monkeypatch: MonkeyPatch, tmp_path: Path):
    current_working_directory = tmp_path / 'wriggle'
    current_working_directory.mkdir()
    monkeypatch.chdir(current_working_directory)
    clear_environment(monkeypatch)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'biobuddies/measles')

    assert measles.cona() == 'measles'


def test_cona_virtual_env(monkeypatch: MonkeyPatch, tmp_path: Path):
    current_working_directory = tmp_path / 'wriggle'
    current_working_directory.mkdir()
    monkeypatch.chdir(current_working_directory)
    clear_environment(monkeypatch)
    monkeypatch.setenv('VIRTUAL_ENV', str(tmp_path / 'measles' / '.venv'))

    assert measles.cona() == 'measles'


def test_cona_current_working_directory(monkeypatch: MonkeyPatch, tmp_path: Path):
    current_working_directory = tmp_path / 'wriggle'
    current_working_directory.mkdir()
    monkeypatch.chdir(current_working_directory)
    clear_environment(monkeypatch)

    assert measles.cona() == 'wriggle'


def test_cona_rejects_bad_characters(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    clear_environment(monkeypatch)
    monkeypatch.setenv('CONA', 'bad name')

    with raises(ValueError, match=r"^Unexpected CONA characters: 'bad name'$"):
        measles.cona()


def test_orgn_eponymous(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    clear_environment(monkeypatch)
    monkeypatch.setenv('ORGN', 'biobuddies')
    monkeypatch.setenv('GITHUB_REPOSITORY_OWNER', 'ton')

    assert measles.orgn() == 'biobuddies'


def test_orgn_github_repository_owner(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    clear_environment(monkeypatch)
    monkeypatch.setenv('GITHUB_REPOSITORY_OWNER', 'biobuddies')

    assert measles.orgn() == 'biobuddies'


def test_orgn_uses_git_remote(monkeypatch: MonkeyPatch, tmp_path: Path):
    repository = tmp_path / 'repo'
    repository.mkdir()
    (repository / '.git').mkdir()
    monkeypatch.chdir(repository)
    clear_environment(monkeypatch)
    monkeypatch.setattr(
        measles, 'check_output', lambda _: b'git@github.com:biobuddies/wriggle.git\n'
    )

    assert measles.orgn() == 'biobuddies'


def test_orgn_unknown(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    clear_environment(monkeypatch)

    assert measles.orgn() == 'github-organization-unknown'


def test_orgn_rejects_bad_characters(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    clear_environment(monkeypatch)
    monkeypatch.setenv('ORGN', 'bad name')

    with raises(ValueError, match=r"^Unexpected ORGN characters: 'bad name'$"):
        measles.orgn()


def test_cookiecutter_yaml_from_stack(monkeypatch: MonkeyPatch, tmp_path: Path):
    template_repository = tmp_path / 'measles'
    generated_repository = tmp_path / 'wriggle'
    template_repository.mkdir()
    generated_repository.mkdir()
    (generated_repository / '.cookiecutter.yaml').write_text('default_context:\n')
    monkeypatch.chdir(template_repository)
    clear_environment(monkeypatch)
    monkeypatch.setenv('CONA', 'wriggle')
    monkeypatch.setattr(
        measles,
        'format_stack',
        lambda: [f'  File "{generated_repository}/.venv/bin/cookiecutter", line 12, in <module>\n'],
    )

    assert measles.cookiecutter_yaml() == {'default_context': None}


def test_python_template_globals(monkeypatch: MonkeyPatch):
    clear_environment(monkeypatch)
    monkeypatch.setattr(
        measles,
        'cookiecutter_yaml',
        lambda: {'default_context': {'python_dependencies': ['djangorestframework', 'requests']}},
    )
    assert measles.python_template_globals() == {
        'has_django': True,
        'python_dependencies': ['djangorestframework', 'requests'],
        'python_test_dependencies': ['pytest', 'pytest-cov', 'pytest-django'],
    }
    monkeypatch.setattr(
        measles,
        'cookiecutter_yaml',
        lambda: {'default_context': {'python_dependencies': ['click']}},
    )
    assert measles.python_template_globals() == {
        'has_django': False,
        'python_dependencies': ['click'],
        'python_test_dependencies': ['pytest', 'pytest-cov'],
    }


def test_init(monkeypatch: MonkeyPatch):
    monkeypatch.setattr(measles, 'cona', lambda: 'measles')
    monkeypatch.setattr(measles, 'orgn', lambda: 'biobuddies')
    monkeypatch.setattr(measles, 'gitignore', lambda languages: f'gitignore:{languages}')
    monkeypatch.setattr(
        measles,
        'python_template_globals',
        lambda: {
            'has_django': True,
            'python_dependencies': ['django'],
            'python_test_dependencies': ['pytest', 'pytest-cov', 'pytest-django'],
        },
    )
    environment = Environment(autoescape=False, extensions=[measles.Measles])  # noqa: S701

    assert (
        environment.from_string(
            '{{ CONA }} {{ ORGN }} {{ has_django }} {{ python_dependencies|join(",") }}'
            ' {{ python_test_dependencies|join(",") }} {{ gitignore("Python") }}'
        ).render()
        == 'measles biobuddies True django pytest,pytest-cov,pytest-django gitignore:Python'
    )
