"""Test downstream repository generation."""

import stat
import tomllib
from json import loads
from os import environ, getenv
from pathlib import Path
from re import sub
from subprocess import STDOUT, CalledProcessError, check_call, check_output

from pytest import fixture, mark, raises
from yaml import safe_dump


@fixture
def cache_environment() -> dict[str, str]:
    home = Path.home()
    cache_home = Path(getenv('XDG_CACHE_HOME', str(home / '.cache')))
    return {
        'MISE_CACHE_DIR': getenv('MISE_CACHE_DIR', str(cache_home / 'mise')),
        'MISE_DATA_DIR': getenv('MISE_DATA_DIR', str(home / '.local' / 'share' / 'mise')),
        'NPM_CONFIG_CACHE': getenv('NPM_CONFIG_CACHE', str(home / '.npm')),
        'UV_CACHE_DIR': getenv('UV_CACHE_DIR', str(cache_home / 'uv')),
    }


def test_missing_cookiecutter_yaml(tmp_path: Path, cache_environment: dict[str, str]):
    environment = check_output(['mise', 'envi']).decode().strip()
    tag_or_branch = check_output(['mise', 'tabr']).decode().strip()
    template = (
        str(Path(__file__).parent)
        if environment == 'local'
        else 'https://github.com/biobuddies/measles.git'
        + (f' --checkout {tag_or_branch}' if tag_or_branch else '')
    )

    assert not (tmp_path / '.cookiecutter.yaml').exists()
    with raises(CalledProcessError) as error:
        check_output(
            ['uvx', 'cookiecutter', '--no-input', '--overwrite-if-exists', *template.split()],
            cwd=tmp_path,
            env={
                'CONA': 'speedrun',
                'HOME': str(tmp_path.parent),
                'ORGN': 'biobuddies',
                'PATH': environ['PATH'],
                'PWD': str(tmp_path),
                **cache_environment,
                **(
                    {'GITHUB_TOKEN': token}
                    if (token := getenv('GITHUB_TOKEN') or getenv('MISE_GITHUB_TOKEN'))
                    else {}
                ),
            },
            stderr=STDOUT,
        )
    assert '.cookiecutter.yaml' in error.value.output.decode()


def test_new_repository_not_django(tmp_path: Path, cache_environment: dict[str, str]):
    repository = Path(__file__).parent
    (tmp_path / '.cookiecutter.yaml').write_text(
        safe_dump(
            {
                'default_context': {
                    'node_dependencies': {'react': '^19.0.0'},
                    'node_dev_dependencies': {'vite': '^7.0.0'},
                    'python_dependencies': ['click'],
                    'python_optional_dependencies': {'test': ['pytest-httpserver']},
                }
            },
            sort_keys=False,
        )
    )
    (tmp_path / '.gitignore').write_text((repository / '.gitignore').read_text())
    env = {
        'CONA': 'wriggle',
        'HOME': str(tmp_path.parent),
        'MISE_GITHUB_ATTESTATIONS': 'false',
        'MISE_GPG_VERIFY': 'false',
        'ORGN': 'biobuddies',
        'PATH': environ['PATH'],
        'PWD': str(tmp_path),
        **cache_environment,
        **(
            {'GITHUB_TOKEN': token}
            if (token := getenv('GITHUB_TOKEN') or getenv('MISE_GITHUB_TOKEN'))
            else {}
        ),
    }
    check_call(
        ['mise', 'cookiecutter', '--edit', str(repository)],
        cwd=tmp_path,
        env={**env, 'MISE_CONFIG_FILE': str(repository / '.config' / 'mise.toml')},
        stderr=STDOUT,
    )
    check_call(['mise', 'trust', '--yes'], cwd=tmp_path, env=env, stderr=STDOUT)
    check_call(['mise', 'install'], cwd=tmp_path, env=env, stderr=STDOUT)
    check_call(
        ['mise', 'pre-commit-all', '--edit', str(repository)], cwd=tmp_path, env=env, stderr=STDOUT
    )

    pyproject = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
    package = loads((tmp_path / 'package.json').read_text())
    assert package['dependencies']['react'] == '^19.0.0'
    assert package['devDependencies']['vite'] == '^7.0.0'
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-httpserver',
    ]
    assert pyproject['tool']['pytest']['ini_options']['norecursedirs'] == [
        '.venv',
        'node_modules',
        '{{cookiecutter.dot}}',
    ]
    assert 'DJANGO_SETTINGS_MODULE' not in pyproject['tool']['pytest']['ini_options']
    assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert not (tmp_path / 'manage.py').exists()
    assert not (tmp_path / 'config' / 'settings.py').exists()
    for link, target in (
        ('AGENTS.md', 'CONTRIBUTING.md'),
        ('CLAUDE.md', 'CONTRIBUTING.md'),
        ('.github/copilot-instructions.md', '../CONTRIBUTING.md'),
    ):
        assert (tmp_path / link).is_symlink()
        assert (tmp_path / link).readlink() == Path(target)


def test_new_repository_yes_django(tmp_path: Path, cache_environment: dict[str, str]):
    repository = Path(__file__).parent
    (tmp_path / '.cookiecutter.yaml').write_text(
        safe_dump(
            {
                'default_context': {
                    'python_dependencies': ['djangorestframework', 'requests'],
                    'python_optional_dependencies': {'test': ['pytest-httpserver']},
                }
            },
            sort_keys=False,
        )
    )
    (tmp_path / '.gitignore').write_text((repository / '.gitignore').read_text())
    env = {
        'CONA': 'speedrun',
        'HOME': str(tmp_path.parent),
        'MISE_GITHUB_ATTESTATIONS': 'false',
        'MISE_GPG_VERIFY': 'false',
        'ORGN': 'biobuddies',
        'PATH': environ['PATH'],
        'PWD': str(tmp_path),
        **cache_environment,
        **(
            {'GITHUB_TOKEN': token}
            if (token := getenv('GITHUB_TOKEN') or getenv('MISE_GITHUB_TOKEN'))
            else {}
        ),
    }
    check_call(
        ['mise', 'cookiecutter', '--edit', str(repository)],
        cwd=tmp_path,
        env={**env, 'MISE_CONFIG_FILE': str(repository / '.config' / 'mise.toml')},
        stderr=STDOUT,
    )
    check_call(['mise', 'trust', '--yes'], cwd=tmp_path, env=env, stderr=STDOUT)
    check_call(['mise', 'install'], cwd=tmp_path, env=env, stderr=STDOUT)
    check_call(
        ['mise', 'pre-commit-all', '--edit', str(repository)], cwd=tmp_path, env=env, stderr=STDOUT
    )
    check_call(['mise', 'test'], cwd=tmp_path, env=env, stderr=STDOUT)

    pyproject = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-django',
        'pytest-httpserver',
    ]
    assert pyproject['tool']['pytest']['ini_options']['norecursedirs'] == [
        '.venv',
        'node_modules',
        '{{cookiecutter.dot}}',
    ]
    assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    for link, target in (
        ('AGENTS.md', 'CONTRIBUTING.md'),
        ('CLAUDE.md', 'CONTRIBUTING.md'),
        ('.github/copilot-instructions.md', '../CONTRIBUTING.md'),
    ):
        assert (tmp_path / link).is_symlink()
        assert (tmp_path / link).readlink() == Path(target)
    assert (tmp_path / 'config' / 'settings.py').exists()
    assert 'def test_manage_check(monkeypatch):' in (tmp_path / 'test_boilerplate.py').read_text()


@mark.parametrize(
    ('codename', 'dependency', 'has_django'),
    (('speedrun', 'django', True), ('wriggle', 'sqlglot', False)),
    ids=('yes-django', 'not-django'),
)
def test_existing_repository(codename: str, dependency: str, has_django: bool):
    downstream = Path.home() / 'code' / codename
    cookiecutter_yaml = downstream / '.cookiecutter.yaml'
    assert cookiecutter_yaml.exists()
    assert 'languages' in cookiecutter_yaml.read_text()
    env = {
        'HOME': environ['HOME'],
        'MISE_TRUSTED_CONFIG_PATHS': str(downstream),
        'PATH': environ['PATH'],
    }
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
    check_call(['mise', 'cookiecutter', '--edit'], cwd=downstream, env=env)
    # mise cookiecutter updated .config/mise.toml; re-run to apply the new postinstall hook
    check_call(['mise', 'install'], cwd=downstream, env=env)

    pyproject = tomllib.loads((downstream / 'pyproject.toml').read_text())
    pytest_options = pyproject['tool']['pytest']['ini_options']
    assert (downstream / '.biobuddies' / 'ruff.toml').exists()
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


def test_readme_bootstrap(tmp_path: Path, cache_environment: dict[str, str]):
    repository = Path(__file__).parent
    environment = check_output(['mise', 'envi']).decode().strip()
    tag_or_branch = check_output(['mise', 'tabr']).decode().strip()
    uv_version = check_output(['mise', 'current', 'uv']).decode().strip()
    replacements = (
        (str(repository), f' --edit {repository}')
        if environment == 'local'
        else (f'https://github.com/biobuddies/measles.git --checkout {tag_or_branch}', '')
        if tag_or_branch != 'main'
        else ('https://github.com/biobuddies/measles.git', '')
    )
    commands = sub(
        r'(cookiecutter .+?) https://github\.com/biobuddies/measles\.git',
        rf'\1 {replacements[0]}',
        sub(
            r'(mise pre-commit-all)',
            rf'\1{replacements[1]}',
            (repository / 'README.md').read_text().split('```bash\n')[1].split('\n```')[0],
        ),
    ).replace('mise use uv@latest', f'mise use uv@{uv_version}')
    env = {
        'CONA': 'speedrun',
        'HOME': str(tmp_path.parent),
        'MISE_GITHUB_ATTESTATIONS': 'false',
        'MISE_GPG_VERIFY': 'false',
        'ORGN': 'biobuddies',
        'PATH': environ['PATH'],
        'PWD': str(tmp_path),
        **cache_environment,
        **(
            {'GITHUB_TOKEN': token}
            if (token := getenv('GITHUB_TOKEN') or getenv('MISE_GITHUB_TOKEN'))
            else {}
        ),
        **({'GITHUB_HEAD_REF': tag_or_branch} if tag_or_branch and environment == 'github' else {}),
    }
    (tmp_path / '.gitignore').write_text((repository / '.gitignore').read_text())
    check_call(
        ['/usr/bin/env', 'bash', '-c', f'set -o errexit -o nounset -o pipefail\n{commands}'],
        cwd=tmp_path,
        env=env,
        stderr=STDOUT,
    )

    pyproject = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-django',
    ]
    assert (tmp_path / 'config' / 'settings.py').exists()
