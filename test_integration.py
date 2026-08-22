"""Test downstream repository generation."""

import stat
import tomllib
from collections.abc import Callable
from json import loads
from os import environ, getenv
from pathlib import Path
from re import MULTILINE, sub
from subprocess import CalledProcessError, check_call, check_output
from typing import Any

from pytest import fixture, mark, raises
from yaml import safe_dump


@fixture
def readme_bootstrap(tmp_path: Path) -> Callable[..., tuple[Path, dict[str, Any]]]:
    home = Path.home()
    cache_home = Path(getenv('XDG_CACHE_HOME', str(home / '.cache')))
    repository = Path(__file__).parent
    environment = check_output(['mise', 'envi']).decode().strip()
    tag_or_branch = check_output(['mise', 'tabr']).decode().strip()
    uv_version = check_output(['mise', 'current', 'uv']).decode().strip()
    cookiecutter_task = (
        loads(check_output(['mise', 'tasks', 'info', 'cookiecutter', '--json']))['run'][0]
        .replace('$(mise tabr)', tag_or_branch)
        .replace('\ncookiecutter', '\nuvx cookiecutter')
    )
    cookiecutter_task = (
        f'set -- --edit {repository}\n{cookiecutter_task}'
        if tag_or_branch != 'main'
        else cookiecutter_task
    )
    pre_commit_arguments = f' --edit {repository}' if tag_or_branch != 'main' else ''
    commands = sub(
        r'^uvx cookiecutter .+$',
        cookiecutter_task,
        sub(
            r'(mise pre-commit-all)',
            rf'\1{pre_commit_arguments}',
            (repository / 'README.md')
            .read_text()
            .split('```bash\n')[1]
            .split('\n```')[0]
            .split('\nEOF\n', 1)[1],
        ),
        flags=MULTILINE,
    ).replace('mise use uv@latest', f'mise use uv@{uv_version}')

    def bootstrap(
        cookiecutter: dict[str, object], *, has_django: bool, **overrides: str
    ) -> tuple[Path, dict[str, Any]]:
        (tmp_path / '.cookiecutter.yaml').write_text(safe_dump(cookiecutter, sort_keys=False))
        (tmp_path / '.gitignore').write_text((repository / '.gitignore').read_text())
        env = {
            'ENVI': 'local',  # don't fail on changes
            'HOME': str(tmp_path.parent),
            'MISE_CACHE_DIR': getenv('MISE_CACHE_DIR', str(cache_home / 'mise')),
            'MISE_DATA_DIR': getenv('MISE_DATA_DIR', str(home / '.local' / 'share' / 'mise')),
            'MISE_GITHUB_ATTESTATIONS': 'false',
            'MISE_GPG_VERIFY': 'false',
            'NPM_CONFIG_CACHE': getenv('NPM_CONFIG_CACHE', str(home / '.npm')),
            'ORGN': 'biobuddies',
            'PATH': f'{tmp_path / ".venv" / "bin"}:{environ["PATH"]}',
            'PWD': str(tmp_path),
            'UV_CACHE_DIR': getenv('UV_CACHE_DIR', str(cache_home / 'uv')),
            **({'GITHUB_TOKEN': token} if (token := getenv('GITHUB_TOKEN')) else {}),
            **(
                {'GITHUB_HEAD_REF': tag_or_branch}
                if tag_or_branch and environment == 'github'
                else {}
            ),
            **overrides,
        }
        check_call(
            ['/usr/bin/env', 'bash', '-c', f'set -o errexit -o nounset -o pipefail\n{commands}'],
            cwd=tmp_path,
            env=env,
        )
        pyproject = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
        assert (
            check_output(['mise', 'cona'], cwd=tmp_path, env=env)
            == (overrides['CONA'] + '\n').encode()
        )
        assert pyproject['tool']['pytest']['ini_options']['norecursedirs'] == [
            '.venv',
            'node_modules',
            '{{cookiecutter.dot}}',
        ]
        assert (
            'DJANGO_SETTINGS_MODULE' in pyproject['tool']['pytest']['ini_options']
        ) == has_django
        assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
        for link, target in (
            ('AGENTS.md', 'CONTRIBUTING.md'),
            ('CLAUDE.md', 'CONTRIBUTING.md'),
            ('.github/copilot-instructions.md', '../CONTRIBUTING.md'),
        ):
            assert (tmp_path / link).is_symlink()
            assert (tmp_path / link).readlink() == Path(target)
        return tmp_path, pyproject

    return bootstrap


def test_missing_cookiecutter_yaml(readme_bootstrap: Callable[..., tuple[Path, dict[str, Any]]]):
    with raises(CalledProcessError):
        readme_bootstrap({}, has_django=False, CONA='speedrun')


def test_new_repository_not_django(readme_bootstrap: Callable[..., tuple[Path, dict[str, Any]]]):
    tmp_path, pyproject = readme_bootstrap(
        {
            'default_context': {
                'node_dependencies': {'react': '^19.0.0'},
                'node_dev_dependencies': {'vite': '^7.0.0'},
                'python_dependencies': ['click'],
                'python_optional_dependencies': {'test': ['pytest-httpserver']},
            }
        },
        has_django=False,
        CONA='wriggle',
    )

    package = loads((tmp_path / 'package.json').read_text())
    assert package['dependencies']['react'] == '^19.0.0'
    assert package['devDependencies']['vite'] == '^7.0.0'
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-httpserver',
    ]
    assert not (tmp_path / 'manage.py').exists()
    assert not (tmp_path / 'config' / 'settings.py').exists()
    assert '    publish:' not in (tmp_path / '.github' / 'workflows' / 'act.yaml').read_text()


def test_new_repository_yes_django(readme_bootstrap: Callable[..., tuple[Path, dict[str, Any]]]):
    tmp_path, pyproject = readme_bootstrap(
        {
            'default_context': {
                'python_dependencies': ['djangorestframework', 'requests'],
                'python_optional_dependencies': {'test': ['pytest-httpserver']},
            }
        },
        has_django=True,
        CONA='speedrun',
    )

    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-django',
        'pytest-httpserver',
    ]
    assert (tmp_path / 'config' / 'settings.py').exists()
    assert 'def test_manage_check(monkeypatch):' in (tmp_path / 'test_boilerplate.py').read_text()


def test_new_repository_publishes_to_pypi(
    readme_bootstrap: Callable[..., tuple[Path, dict[str, Any]]],
):
    tmp_path, _ = readme_bootstrap(
        {'default_context': {'publish_to_pypi': True}}, has_django=False, CONA='package'
    )

    workflow = (tmp_path / '.github' / 'workflows' / 'act.yaml').read_text()
    assert "        if: github.event_name == 'release'" in workflow
    assert '            - uses: pypa/gh-action-pypi-publish@release/v1' in workflow
    assert '    release:' in workflow


@mark.parametrize(
    ('codename', 'dependency', 'has_django'),
    (('speedrun', 'django', True), ('wriggle', 'sqlglot', False)),
    ids=('yes-django', 'not-django'),
)
def test_existing_repository(codename: str, dependency: str, has_django: bool):
    downstream = Path.home() / 'code' / codename
    cookiecutter_yaml = downstream / '.cookiecutter.yaml'
    env = {
        'CONA': codename,
        'ENVI': 'local',  # don't fail on changes
        'HOME': environ['HOME'],
        'MISE_TRUSTED_CONFIG_PATHS': str(downstream),
        'ORGN': 'biobuddies',
        'PATH': f'{downstream / ".venv" / "bin"}:{environ["PATH"]}',
        **({'GITHUB_TOKEN': token} if (token := getenv('GITHUB_TOKEN')) else {}),
    }
    if not cookiecutter_yaml.exists():
        cookiecutter_yaml.write_text(
            safe_dump({
                'default_context': {'languages': 'Python', 'python_dependencies': [dependency]}
            })
        )
        check_call(
            [
                'uvx',
                'cookiecutter',
                '--config-file',
                '.cookiecutter.yaml',
                '--no-input',
                '--overwrite-if-exists',
                str(Path(__file__).parent),
            ],
            cwd=downstream,
            env=env,
        )
    assert 'languages' in cookiecutter_yaml.read_text()
    assert check_output(['mise', 'cona'], cwd=downstream, env=env) == f'{codename}\n'.encode()
    assert (
        check_output(
            ['mise', 'x', '--', 'python', '-c', 'from pathlib import Path; print(Path.cwd().name)'],
            cwd=downstream,
            env=env,
        )
        == f'{codename}\n'.encode()
    )

    check_call(['mise', 'install'], cwd=downstream, env=env)
    try:
        check_call(['mise', 'pre-commit-all', '--edit'], cwd=downstream, env=env)
    except CalledProcessError:
        (downstream / '.git' / 'index.lock').unlink(missing_ok=True)
        check_call(['mise', 'pre-commit'], cwd=downstream, env=env)
    # In case mise cookiecutter updated the postinstall hook in .config/mise.toml
    check_call(['mise', 'install'], cwd=downstream, env=env)

    pyproject = tomllib.loads((downstream / 'pyproject.toml').read_text())
    pytest_options = pyproject['tool']['pytest']['ini_options']
    assert (downstream / '.biobuddies' / 'ruff.toml').exists()
    assert (downstream / '.gitignore').exists()
    assert dependency in pyproject['project']['dependencies']
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        *(['pytest-django'] if has_django else []),
    ]
    assert pytest_options['norecursedirs'] == ['.venv', 'node_modules', '{{cookiecutter.dot}}']
    assert ('DJANGO_SETTINGS_MODULE' in pytest_options) == has_django
    assert (downstream / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert (downstream / 'manage.py').exists() == has_django
    assert (downstream / 'config' / 'settings.py').exists() == has_django
