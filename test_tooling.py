"""Integration tests for tools and configuration."""

import stat
import sys
import tomllib
from base64 import b64encode
from io import BytesIO
from json import dumps, loads
from os import environ, getenv
from pathlib import Path
from re import match
from subprocess import STDOUT, CalledProcessError, check_call, check_output
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

from _pytest.monkeypatch import MonkeyPatch
from jinja2 import Environment
from pytest import CaptureFixture, fail, fixture, mark, raises

import measles

# Four Letter AbbreviatioNs (FLANs)


def test_four_letter_abbreviations():
    assert check_output(['mise', 'cona']) == b'measles\n'

    assert check_output(['mise', 'envi']) == b'github\n' if getenv('GITHUB_ACTIONS') else b'local\n'

    giha = check_output(['mise', 'giha'])
    assert match(rb'^[0-9a-f]{40}(-dirty)?\n$', giha)
    is_dirty = bool(check_output(['git', 'status', '--porcelain', '--untracked-files=no']))
    assert giha.endswith(b'-dirty\n') == is_dirty

    assert check_output(['mise', 'orgn']) == b'biobuddies\n'

    assert check_output(
        ['mise', 'tabr'],
        env={
            'MISE_TRUSTED_CONFIG_PATHS': getenv('MISE_TRUSTED_CONFIG_PATHS', ''),
            'PATH': environ['PATH'],
        },
    ) == (
        b''
        if is_dirty
        else check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip() + b'\n'
    )

    assert check_output(['mise', 'fqdn']) == b''


@mark.parametrize(
    ('git_describe', 'tabr'),
    (
        # Happy paths
        ('remotes/origin/mybranch', 'mybranch'),
        ('heads/mybranch', 'mybranch'),
        ('tags/v2025.02.03', 'v2025.02.03'),
        # Error
        ('heads/mybranch-dirty', ''),
    ),
)
def test_tabr(git_describe: str, tabr: str):
    original = loads(check_output(['mise', 'tasks', 'info', 'tabr', '--json']))['run'][0].replace(
        '\\n', '\n'
    )
    target = 'git describe --all --dirty --exact-match'
    assert target in original
    mocked = original.replace(target, f'echo "{git_describe}"')
    output = check_output(['/usr/bin/env', 'bash', '-c', mocked], env={}).decode().strip()
    assert output == tabr


@mark.parametrize(
    ('tabr', 'domain', 'fqdn'),
    (
        ('main', '', ''),
        ('', 'cov.ing', ''),
        ('main', 'cov.ing', 'cov.ing'),
        ('my-feature', '', ''),
        ('my-feature', 'cov.ing', 'my-feature.cov.ing'),
    ),
)
def test_fqdn(tmp_path: Path, tabr: str, domain: str, fqdn: str):
    tabr_task = loads(check_output(['mise', 'tasks', 'info', 'tabr', '--json']))['run'][0].replace(
        '\\n', '\n'
    )
    template = (
        (Path(__file__).parent / '{{cookiecutter.dot}}' / '.config' / 'mise.toml')
        .read_text()
        .split('[tasks.fqdn]\n', 1)[1]
        .split('[tasks.giha]')[0]
    )
    if domain:
        fqdn_task = (
            template
            .strip()
            .replace('{%- if cookiecutter.domain_name %}\n', '')
            .replace("\n{%- else %}\nrun = ''\n{%- endif %}", '')
            .replace('{{ cookiecutter.domain_name }}', domain)
        )
    else:
        fqdn_task = "run = ''\n"
    (tmp_path / '.config').mkdir()
    (tmp_path / '.config' / 'mise.toml').write_text(
        f"[tasks.tabr]\nrun = '''\n{tabr_task}'''\n\n[tasks.fqdn]\n{fqdn_task}\n"
    )
    mock_git = tmp_path / 'git'
    describe = f'heads/{tabr}-dirty' if tabr == '' else f'heads/{tabr}'
    mock_git.write_text(f'#!/usr/bin/env bash\necho "{describe}"\n')
    mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC)
    env = {'MISE_TRUSTED_CONFIG_PATHS': str(tmp_path), 'PATH': f'{tmp_path}:{environ["PATH"]}'}
    output = check_output(['mise', 'fqdn'], cwd=tmp_path, env=env).decode().strip()
    assert output == fqdn


# (5+ letter) line keepers


@mark.parametrize(
    ('git_output', 'output'),
    (
        ('bad path.py\\0', 'bad path.py\n'),
        ('bad\\tpath.py\\0', 'bad\tpath.py\n'),
        ('bad\\npath.py\\0', 'bad\npath.py\n'),
    ),
)
def test_no_field_separators(tmp_path: Path, git_output: str, output: str):
    task = loads(check_output(['mise', 'tasks', 'info', 'no-field-separators', '--json']))['run'][
        0
    ].replace('\\n', '\n')
    mock_git = tmp_path / 'git'
    mock_git.write_text(f'#!/usr/bin/env bash\nprintf "{git_output}"\n')
    mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC)
    environment = {'PATH': f'{tmp_path}:{environ["PATH"]}'}
    with raises(CalledProcessError) as error:
        check_output(['/usr/bin/env', 'bash', '-c', task], env=environment, stderr=-1)
    assert error.value.returncode == 1
    assert error.value.output.decode().endswith(output)


def test_run_on_sources():
    binary_path = Path('test.zip')
    try:
        binary_path.write_bytes(
            b'PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        )
        with TemporaryDirectory() as tmpdir:
            mock_git = Path(tmpdir) / 'git'
            mock_git.write_text(
                f'#!/usr/bin/env bash\n[[ $1 == grep ]] && exit 1\necho {binary_path}\n'
            )
            mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC)
            env = environ.copy()
            env['PATH'] = f'{tmpdir}:{env["PATH"]}'
            output = check_output(
                ['mise', 'run-on-sources', 'echo', str(binary_path)], env=env
            ).decode()
        assert str(binary_path) not in output
    finally:
        binary_path.unlink(missing_ok=True)


# Line changers


@fixture
def gitignore_request(monkeypatch: MonkeyPatch) -> SimpleNamespace:
    captured_request = SimpleNamespace(request=None)

    def fake_urlopen(request: Request) -> BytesIO:
        if captured_request.request is not None:
            fail('urlopen called twice')
        captured_request.request = request
        return BytesIO(
            dumps({'content': b64encode(b'/site\n').decode(), 'sha': 'c0def00d'}).encode()
        )

    monkeypatch.setattr(measles, 'urlopen', fake_urlopen)
    return captured_request


def test_gitignore_no_token_or_sed_substitution(
    monkeypatch: MonkeyPatch, gitignore_request: SimpleNamespace
):
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)

    result = measles.gitignore('Python')
    request = gitignore_request.request

    assert result == '# Python=c0def00d\n/site\n'
    assert request is not None
    assert (
        request.full_url
        == 'https://api.github.com/repos/github/gitignore/contents/Python.gitignore?ref=main'
    )
    assert request.get_header('Authorization') is None


def test_gitignore_with_token_and_sed_substitution(
    monkeypatch: MonkeyPatch, tmp_path: Path, gitignore_request: SimpleNamespace
):
    (tmp_path / '.gitignore.sed').write_text('s,^/site$,/site/ton/,\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('GITHUB_TOKEN', 'test-token')

    result = measles.gitignore('Python')
    request = gitignore_request.request

    assert result == '# Python=c0def00d\n/site/ton/\n'
    assert request is not None
    assert (
        request.full_url
        == 'https://api.github.com/repos/github/gitignore/contents/Python.gitignore?ref=main'
    )
    assert request.get_header('Authorization') == 'Bearer test-token'


def raise_http_error(_: Any) -> Any:
    raise HTTPError(
        'https://api.github.com/repos/github/gitignore/contents/Python.gitignore?ref=main',
        429,
        'Too Many Requests',
        None,  # pyrefly: ignore[bad-argument-type]
        None,
    )


def test_gitignore_fallback_on_api_error(monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]):
    vendored_gitignore = '# header\n# hashes\n# Python=oldf00d\nlogs\nnode_modules/\n'

    def fake_read_text(path: Path) -> str:
        if path.name == '.gitignore':
            return vendored_gitignore
        raise AssertionError(path)

    monkeypatch.setattr(measles.Path, 'read_text', fake_read_text)
    monkeypatch.setattr(measles, 'stderr', sys.stderr)
    monkeypatch.setattr(measles, 'urlopen', raise_http_error)

    result = measles.gitignore('Python')
    captured = capsys.readouterr()

    assert result == 'logs\nnode_modules/\n'
    assert captured.err == (
        'Warning: falling back to vendored .gitignore after GitHub fetch failed: '
        'HTTP 429 Too Many Requests\n'
    )


def test_prettier():
    test_path = Path('test-prettier.j2.html')
    try:
        test_path.write_text(
            '<html><body>\n{% for item in items %}<div>{{item}}</div>{% endfor %}\n</body></html>\n'
        )
        with TemporaryDirectory() as tmpdir:
            mock_git = Path(tmpdir) / 'git'
            mock_git.write_text(f'#!/usr/bin/env bash\necho {test_path}\n')
            mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC)
            env = environ.copy()
            env['PATH'] = f'{tmpdir}:{env["PATH"]}'
            check_output(['mise', 'prettier-write'], env=env)
        assert test_path.read_text() == (
            '<html>\n'
            '    <body>\n'
            '        {% for item in items %}<div>{{ item }}</div>{% endfor %}\n'
            '    </body>\n'
            '</html>\n'
        )
    finally:
        test_path.unlink(missing_ok=True)


def test_typos():
    input_path = Path('wxperiment-\xb5.yml')  # noqa: RUF100  # noqa: typos
    output_path = Path('experiment-\u03bc.yaml')
    try:
        input_path.write_text('wxperiment:\n  - \xb5\n  yml\n')  # noqa: RUF100  # noqa: typos
        check_output(['mise', 'typos', str(input_path)])
        assert output_path.read_text() == 'experiment:\n  - \u03bc\n  yaml\n'
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def render_post_gen(
    globals_: dict[str, object], tmp_path: Path, uv_script: str
) -> tuple[str, Path]:
    tmp_path.mkdir()
    boilerplate_template_path = (
        Path(__file__).parent / '{{cookiecutter.dot}}' / 'test_boilerplate.py'
    )
    pyproject_template = (
        Path(__file__).parent / '{{cookiecutter.dot}}' / 'pyproject.toml'
    ).read_text()
    boilerplate = (
        Environment(autoescape=False)  # noqa: S701
        .from_string(boilerplate_template_path.read_text())
        .render(**globals_)
    )
    hook_template = (Path(__file__).parent / 'hooks' / 'post_gen_project.bash').read_text()
    pyproject = (
        Environment(autoescape=False)  # noqa: S701
        .from_string(pyproject_template)
        .render(**globals_, cookiecutter={'python_optional_dependencies': {}})
    )
    fake_uv = tmp_path / 'uv'
    fake_uv.write_text(uv_script)
    fake_uv.chmod(fake_uv.stat().st_mode | stat.S_IEXEC)
    (tmp_path / '.github').mkdir()
    (tmp_path / 'pyproject.toml').write_text(pyproject)
    (tmp_path / 'test_boilerplate.py').write_text(boilerplate)
    (tmp_path / 'run-post-gen.bash').write_text(
        Environment(autoescape=False).from_string(hook_template).render(**globals_)  # noqa: S701
    )
    check_call(
        ['/usr/bin/env', 'bash', 'run-post-gen.bash'],
        cwd=tmp_path,
        env={'PATH': f'{tmp_path}:{environ["PATH"]}'},
    )
    return pyproject, tmp_path


def test_post_gen_project_bash(tmp_path: Path):
    yes_django_pyproject, yes_django_project = render_post_gen(
        {
            'has_django': True,
            'python_dependencies': ['djangorestframework', 'click'],
            'python_test_dependencies': ['pytest', 'pytest-cov', 'pytest-django'],
        },
        tmp_path / 'yes-django',
        '#!/usr/bin/env bash\n'
        'set -o errexit -o nounset -o pipefail\n'
        'mkdir -p config\n'
        "printf '%s\\n' '#!/usr/bin/env python' > manage.py\n"
        "printf '%s\\n' \"SECRET_KEY = 'django-insecure-test-key'\" > config/settings.py\n"
        "printf '%s\\n' '' > config/__init__.py\n"
        "printf '%s\\n' '' > config/asgi.py\n"
        "printf '%s\\n' '' > config/urls.py\n"
        "printf '%s\\n' '' > config/wsgi.py\n",
    )
    not_django_pyproject, not_django_project = render_post_gen(
        {
            'has_django': False,
            'python_dependencies': ['click'],
            'python_test_dependencies': ['pytest', 'pytest-cov'],
        },
        tmp_path / 'not-django',
        '#!/usr/bin/env bash\nexit 1\n',
    )

    assert 'pytest-django' in yes_django_pyproject
    assert (
        '[tool.pytest.ini_options]\n'
        "DJANGO_SETTINGS_MODULE = 'config.settings'\n"
        "norecursedirs = ['{{cookiecutter.dot}}']"
    ) in yes_django_pyproject
    assert (yes_django_project / 'manage.py').exists()
    assert (yes_django_project / 'config' / 'settings.py').exists()
    assert (yes_django_project / 'test_boilerplate.py').read_text().rstrip().splitlines() == [
        '"""Nominally cover autogenerated files.',
        '',
        'AUTOGENERATED by https://github.com/biobuddies/measles',
        '"""',
        'from importlib import import_module',
        '',
        '',
        'def test_manage_check(monkeypatch):',
        "    monkeypatch.setattr('sys.argv', ['/home/biobuddy/code/newthing/manage.py', 'check'])",
        "    import_module('manage').main()",
    ]

    assert 'pytest-django' not in not_django_pyproject
    assert (
        "[tool.pytest.ini_options]\n\nnorecursedirs = ['{{cookiecutter.dot}}']"
    ) in not_django_pyproject
    assert "DJANGO_SETTINGS_MODULE = 'config.settings'" not in not_django_pyproject
    assert not (not_django_project / 'manage.py').exists()
    assert not (not_django_project / 'config' / 'settings.py').exists()
    assert (not_django_project / 'test_boilerplate.py').read_text().rstrip().splitlines() == [
        '"""Nominally cover autogenerated files.',
        '',
        'AUTOGENERATED by https://github.com/biobuddies/measles',
        '"""',
        '# This file is only populated for Django projects.',
    ]


def test_end_of_file_fixer():
    test_path = Path('test.sed')
    try:
        test_path.write_text('s/old/new/\n\n')
        with TemporaryDirectory() as tmpdir:
            mock_git = Path(tmpdir) / 'git'
            mock_git.write_text(f'#!/usr/bin/env bash\necho {test_path}\n')
            mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC)
            env = environ.copy()
            env['PATH'] = f'{tmpdir}:{env["PATH"]}'
            with raises(CalledProcessError):
                check_output(['mise', 'end-of-file-fixer'], env=env)
        assert test_path.read_text() == 's/old/new/\n'
    finally:
        test_path.unlink(missing_ok=True)


# Downstream usage


def test_existing_unframed_repository_wriggle():
    # Check arrangement
    wriggle = Path.home() / 'code' / 'wriggle'
    cookiecutter_yaml = wriggle / '.cookiecutter.yaml'
    assert cookiecutter_yaml.exists()
    assert 'languages' in cookiecutter_yaml.read_text()
    env = {
        'HOME': environ['HOME'],
        'MISE_TRUSTED_CONFIG_PATHS': str(wriggle),
        'PATH': environ['PATH'],
    }
    assert check_output(['mise', 'cona'], cwd=wriggle, env=env) == b'wriggle\n'
    assert (
        check_output(
            ['mise', 'x', '--', 'python', '-c', 'from pathlib import Path; print(Path.cwd().name)'],
            cwd=wriggle,
            env=env,
        )
        == b'wriggle\n'
    )
    manage_path = wriggle / 'manage.py'
    settings_path = wriggle / 'config' / 'settings.py'
    had_manage = manage_path.exists()
    had_settings = settings_path.exists()

    # Act
    check_call(['mise', 'install'], cwd=wriggle, env=env)
    check_call(['mise', 'cookiecutter', '--edit'], cwd=wriggle, env=env)
    # mise cookiecutter updated .config/mise.toml; re-run to apply new postinstall
    # hook which generates pre-commit hook via mise generate pre-commit
    check_call(['mise', 'install'], cwd=wriggle, env=env)

    # Assert
    pyproject = tomllib.loads((wriggle / 'pyproject.toml').read_text())
    assert (wriggle / '.biobuddies' / 'ruff.toml').exists()
    assert 'sqlglot' in pyproject['project']['dependencies']
    assert pyproject['project']['optional-dependencies']['test'] == ['pytest', 'pytest-cov']
    pyproject_text = (wriggle / 'pyproject.toml').read_text()
    assert "[tool.pytest.ini_options]\n\nnorecursedirs = ['{{cookiecutter.dot}}']" in pyproject_text
    assert 'DJANGO_SETTINGS_MODULE' not in pyproject_text
    assert (wriggle / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert manage_path.exists() == had_manage
    assert settings_path.exists() == had_settings


def test_new_django_repository_bootstrap_speedrun(tmp_path: Path):
    readme = (Path(__file__).parent / 'README.md').read_text()
    bootstrap = readme.split('```bash\n')[1].split('\n```')[0]
    environment = check_output(['mise', 'envi']).decode().strip()
    tag_or_branch = check_output(['mise', 'tabr']).decode().strip()
    if environment == 'local':
        bootstrap = bootstrap.replace(
            'https://github.com/biobuddies/measles.git', f'{Path(__file__).parent}'
        )
        bootstrap = bootstrap.replace(
            'mise pre-commit-all', f'mise pre-commit-all --edit {Path(__file__).parent}'
        )
    elif environment == 'github' and tag_or_branch != 'main':
        bootstrap = bootstrap.replace(
            'https://github.com/biobuddies/measles.git',
            f'https://github.com/biobuddies/measles.git --checkout {tag_or_branch}',
        )
    elif environment == 'github' and tag_or_branch == 'main':
        pass
    else:
        raise RuntimeError(f'Unsupported {environment=} {tag_or_branch=}')

    cache_directory = (
        Path(__file__).parent / '.cache' / 'test_new_django_repository_bootstrap_speedrun'
    )
    cache_directory.mkdir(parents=True, exist_ok=True)
    env = {
        'CONA': 'speedrun',
        'HOME': str(tmp_path.parent),
        'MISE_CACHE_DIR': str(cache_directory / 'mise-cache'),
        'MISE_DATA_DIR': str(cache_directory / 'mise-data'),
        'MISE_GITHUB_ATTESTATIONS': 'false',
        'MISE_GPG_VERIFY': 'false',
        'NPM_CONFIG_CACHE': str(cache_directory / 'npm'),
        'ORGN': 'biobuddies',
        'PATH': environ['PATH'],
        'UV_CACHE_DIR': str(cache_directory / 'uv'),
        'XDG_CACHE_HOME': str(cache_directory),
    }
    check_call(['mise', 'trust', '--yes'], cwd=tmp_path, env=env)
    check_call(
        [
            '/usr/bin/env',
            'bash',
            '-c',
            f'set -o errexit -o nounset -o pipefail -o xtrace\n{bootstrap}',
        ],
        cwd=tmp_path,
        env=env,
        stderr=STDOUT,
    )

    pyproject_text = (tmp_path / 'pyproject.toml').read_text()
    pyproject = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-django',
    ]
    assert (
        '[tool.pytest.ini_options]\n'
        "DJANGO_SETTINGS_MODULE = 'config.settings'\n"
        "norecursedirs = ['{{cookiecutter.dot}}']"
    ) in pyproject_text
    assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert (tmp_path / 'AGENTS.md').is_symlink()
    assert (tmp_path / 'CLAUDE.md').is_symlink()
    assert (tmp_path / '.github' / 'copilot-instructions.md').is_symlink()
    assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert (tmp_path / 'config' / 'settings.py').exists()
    assert (tmp_path / 'test_boilerplate.py').read_text().rstrip().splitlines() == [
        '"""Nominally cover autogenerated files.',
        '',
        'AUTOGENERATED by https://github.com/biobuddies/measles',
        '"""',
        'from importlib import import_module',
        '',
        '',
        'def test_manage_check(monkeypatch):',
        "    monkeypatch.setattr('sys.argv', ['/home/biobuddy/code/newthing/manage.py', 'check'])",
        "    import_module('manage').main()",
    ]
