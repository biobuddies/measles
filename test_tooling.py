"""Integration tests for tools and configuration."""

import stat
import sys
from base64 import b64encode
from io import BytesIO
from json import dumps, loads
import tomllib
from os import environ, getenv
from pathlib import Path
from re import match, sub
from subprocess import STDOUT, CalledProcessError, check_call, check_output
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

from jinja2 import Environment
from _pytest.monkeypatch import MonkeyPatch
from pytest import CaptureFixture, fail, fixture, mark, raises

import measles
from measles import Measles

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


@mark.parametrize(
    ('python_dependencies', 'has_django', 'python_test_dependencies'),
    (
        (['django>=5'], True, ['pytest', 'pytest-cov', 'pytest-django']),
        (['djangorestframework'], True, ['pytest', 'pytest-cov', 'pytest-django']),
        (['click'], False, ['pytest', 'pytest-cov']),
    ),
)
def test_measles_globals(
    monkeypatch: MonkeyPatch,
    python_dependencies: list[str],
    has_django: bool,
    python_test_dependencies: list[str],
):
    boilerplate = 'from importlib import import_module\n'
    monkeypatch.setattr(measles, 'cona', lambda: 'measles')
    monkeypatch.setattr(measles, 'orgn', lambda: 'biobuddies')
    monkeypatch.setattr(
        measles,
        'safe_load',
        lambda _: {'default_context': {'python_dependencies': python_dependencies}},
    )
    monkeypatch.setattr(
        measles.Path,
        'read_text',
        lambda path: (
            boilerplate if path.name == 'django_boilerplate.py' else 'default_context:\n'
        ),
    )
    environment = Environment(autoescape=True)

    Measles(environment)

    assert environment.globals['CONA'] == 'measles'
    assert environment.globals['ORGN'] == 'biobuddies'
    assert environment.globals['has_django'] == has_django
    assert environment.globals['python_dependencies'] == python_dependencies
    assert environment.globals['python_test_dependencies'] == python_test_dependencies
    assert loads(environment.globals['django_test_boilerplate']) == boilerplate


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


def test_existing_repository():
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

    # Act
    check_call(['mise', 'install'], cwd=wriggle, env=env)
    check_call(['mise', 'cookiecutter', '--edit'], cwd=wriggle, env=env)
    # mise cookiecutter updated .config/mise.toml; re-run to apply new postinstall
    # hook which generates pre-commit hook via mise generate pre-commit
    check_call(['mise', 'install'], cwd=wriggle, env=env)

    # Assert
    pyproject = tomllib.loads((wriggle / 'pyproject.toml').read_text())
    assert (wriggle / '.biobuddies' / 'ruff.toml').exists()
    assert 'sqlglot' in (wriggle / 'pyproject.toml').read_text()
    assert pyproject['project']['optional-dependencies']['test'] == ['pytest', 'pytest-cov']
    assert 'DJANGO_SETTINGS_MODULE' not in (wriggle / 'pyproject.toml').read_text()
    assert (wriggle / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert not (wriggle / 'manage.py').exists()
    assert not (wriggle / 'config' / 'settings.py').exists()
    assert not (wriggle / 'config' / 'test_boilerplate.py').exists()


@mark.skip('complex malfunction in django detection')
def test_new_repository_bootstrap(tmp_path: Path):
    readme = (Path(__file__).parent / 'README.md').read_text()
    original = readme.split('```bash\n')[1].split('\n```')[0]

    environment = check_output(['mise', 'envi']).decode().strip()
    tag_or_branch = check_output(['mise', 'tabr']).decode().strip()

    # Use local files for speed and to avoid rate limits
    if environment == 'local':
        replacements = (str(Path(__file__).parent), f' --edit {Path(__file__).parent}')
    # Use URLs for parity with production
    elif tag_or_branch != 'main':
        replacements = (f'https://github.com/biobuddies/measles.git --checkout {tag_or_branch}', '')
    else:
        replacements = 'https://github.com/biobuddies/measles.git', ''

    commands = sub(
        r'(cookiecutter .+?) https://github\.com/biobuddies/measles\.git',
        rf'\1 {replacements[0]}',
        sub(r'(mise pre-commit-all)', rf'\1{replacements[1]}', original),
    )
    env = {
        'CONA': 'speedrun',
        'HOME': str(tmp_path.parent),
        'MISE_GITHUB_ATTESTATIONS': 'false',
        'MISE_GPG_VERIFY': 'false',
        'ORGN': 'biobuddies',
        'PATH': environ['PATH'],
        **({'GITHUB_HEAD_REF': tag_or_branch} if tag_or_branch and environment == 'github' else {}),
    }
    check_call(
        [
            '/usr/bin/env',
            'bash',
            '-c',
            f'set -o errexit -o nounset -o pipefail -o xtrace\n{commands}',
        ],
        cwd=tmp_path,
        env=env,
    )
    pyproject = tomllib.loads((tmp_path / 'pyproject.toml').read_text())
    assert pyproject['project']['optional-dependencies']['test'] == [
        'pytest',
        'pytest-cov',
        'pytest-django',
    ]
    assert "DJANGO_SETTINGS_MODULE = 'config.settings'" in (tmp_path / 'pyproject.toml').read_text()
    assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert (tmp_path / 'AGENTS.md').is_symlink()
    assert (tmp_path / 'CLAUDE.md').is_symlink()
    assert (tmp_path / '.github' / 'copilot-instructions.md').is_symlink()
    assert (tmp_path / '.git' / 'hooks' / 'pre-commit').stat().st_mode & stat.S_IXUSR
    assert (tmp_path / 'config' / 'settings.py').exists()
    assert (tmp_path / 'config' / 'test_boilerplate.py').exists()
    check_call(['uv', 'run', 'pytest', 'config/test_boilerplate.py'], cwd=tmp_path, env=env)

    def git_text(*args: str) -> str:
        return check_output(
            ['git', *args],
            cwd=tmp_path,
            env={
                **env,
                'GIT_AUTHOR_EMAIL': 'test@example.com',
                'GIT_AUTHOR_NAME': 'Test User',
                'GIT_COMMITTER_EMAIL': 'test@example.com',
                'GIT_COMMITTER_NAME': 'Test User',
            },
            stderr=STDOUT,
            text=True,
        )

    git_text('add', '--all')
    status_before_failed_commit = git_text('status', '--short')
    diffstat_before_failed_commit = git_text('diff', '--cached', '--stat')
    with raises(CalledProcessError) as error:
        git_text('commit', '--message', 'Initial commit', '--no-gpg-sign')
    status_after_failed_commit = git_text('status', '--short')
    diffstat_after_failed_commit = git_text('diff', '--stat')

    assert status_after_failed_commit, '\n'.join(
        (
            'pre-commit failed without changing the working tree',
            f'status before failed commit:\n{status_before_failed_commit}',
            f'diffstat before failed commit:\n{diffstat_before_failed_commit}',
            f'diffstat after failed commit:\n{diffstat_after_failed_commit}',
            f'commit output:\n{error.value.output}',
        )
    )

    git_text('add', '--all')
    status_before_successful_commit = git_text('status', '--short')
    diffstat_before_successful_commit = git_text('diff', '--cached', '--stat')
    successful_commit_output = git_text('commit', '--message', 'Initial commit', '--no-gpg-sign')
    final_status = git_text('status', '--short')

    assert not final_status, '\n'.join(
        (
            f'status before successful commit:\n{status_before_successful_commit}',
            f'diffstat before successful commit:\n{diffstat_before_successful_commit}',
            f'commit output:\n{successful_commit_output}',
            f'final status:\n{final_status}',
        )
    )
