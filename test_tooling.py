"""Integration tests for tools and configuration."""

import stat
import sys
from base64 import b64encode
from io import BytesIO
from json import dumps, loads
from os import environ, getenv
from pathlib import Path
from re import match
from subprocess import DEVNULL, STDOUT, CalledProcessError, check_call, check_output
from tempfile import TemporaryDirectory
from textwrap import dedent
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

from jinja2 import Environment
from pytest import CaptureFixture, MonkeyPatch, fail, fixture, mark, raises

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


def verbatim_mise_task(name: str) -> str:
    return loads(check_output(['mise', 'tasks', 'info', name, '--json']))['run'][0].replace(
        '\\n', '\n'
    )


def replaced_mise_task(name: str, replacements: dict[str, str]) -> str:
    task = verbatim_mise_task(name)
    for old, new in replacements.items():
        assert old in task
        task = task.replace(old, new)
    return task


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
    task = replaced_mise_task(
        'tabr', {'git describe --all --dirty --exact-match': f'echo "{git_describe}"'}
    )
    output = check_output(['/usr/bin/env', 'bash', '-c', task], env={}).decode().strip()
    assert output == tabr


@mark.parametrize(
    'case',
    (
        # Upstream, local, feature branch, files
        ('measles', {}, 'fix-something-in-measles', [], '.'),
        # Upstream, GitHub Actions, feature branch, files
        # mise tabr uses GITHUB_HEAD_REF
        (
            'measles',
            {'GITHUB_ACTIONS': 'true', 'GITHUB_WORKSPACE': '/home/runner/work/measles/measles'},
            'fix-something-in-measles',
            [],
            '.',
        ),
        # Upstream, GitHub Actions, main branch, HTTPS
        (
            'measles',
            {'GITHUB_ACTIONS': 'true', 'GITHUB_WORKSPACE': '/home/runner/work/measles/measles'},
            'main',
            [],
            'https://github.com/biobuddies/measles.git',
        ),
        # Downstream, local, files
        ('speedrun', {}, 'downstream-feature', ['--edit'], '/home/biobuddy/code/measles'),
        # Downstream, local, HTTPS
        ('speedrun', {}, 'downstream-feature', [], 'https://github.com/biobuddies/measles.git'),
        # Downstream, GitHub Actions, HTTPS
        (
            'speedrun',
            {'GITHUB_ACTIONS': 'true', 'GITHUB_WORKSPACE': '/home/runner/work/speedrun/speedrun'},
            'downstream-feature',
            [],
            'https://github.com/biobuddies/measles.git',
        ),
    ),
)
def test_cookiecutter(case: tuple[str, dict[str, str], str, list[str], str]):
    codename, environment, branch, arguments, expected = case
    task = replaced_mise_task(
        'cookiecutter',
        {
            'cookiecutter --config-file': 'echo cookiecutter --config-file',
            'tabr=$(mise tabr)': f'tabr={branch}',
        },
    )

    output = (
        check_output(
            ['/usr/bin/env', 'bash', '-c', task, 'cookiecutter', *arguments],
            env={
                'CONA': codename,
                'HOME': '/home/biobuddy',
                'ORGN': 'biobuddies',
                'PATH': environ['PATH'],
                **environment,
            },
        )
        .decode()
        .split()[1:]
    )

    assert output == [
        '--config-file',
        '.cookiecutter.yaml',
        '--no-input',
        '--overwrite-if-exists',
        expected,
    ]


@mark.parametrize(
    ('tabr', 'domain', 'event', 'fqdn'),
    (
        ('main', '', '', ''),
        ('', 'cov.ing', '', ''),
        ('main', 'cov.ing', '', 'cov.ing'),
        ('my-feature', '', '', ''),
        ('my-feature', 'cov.ing', '', 'my-feature.cov.ing'),
        ('v2026.34.01', 'cov.ing', 'release', 'cov.ing'),
    ),
)
def test_fqdn(tmp_path: Path, tabr: str, domain: str, event: str, fqdn: str):
    tabr_task = replaced_mise_task(
        'tabr',
        {
            'git describe --all --dirty --exact-match': (
                f'echo "heads/{tabr}-dirty"' if tabr == '' else f'echo "heads/{tabr}"'
            )
        },
    )
    template = (
        (Path(__file__).parent / '{{cookiecutter.dot}}' / '.config' / 'mise.j2.toml')
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
    env = {
        'GITHUB_EVENT_NAME': event,
        'MISE_TRUSTED_CONFIG_PATHS': str(tmp_path),
        'PATH': environ['PATH'],
    }
    output = check_output(['mise', 'fqdn'], cwd=tmp_path, env=env).decode().strip()
    assert output == fqdn


# (5+ letter) line keepers


def write_mock_executable(path: Path, body: str) -> None:
    path.write_text(
        '#!/usr/bin/env bash\nset -o errexit -o nounset -o pipefail\n' + dedent(body).lstrip()
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@mark.parametrize('docker_files', ((), ('Dockerfile',), ('Dockerfile', 'compose.yaml')))
def test_build(tmp_path: Path, docker_files: tuple[str, ...]):
    calls = tmp_path / 'calls'
    environment = {'CALLS': str(calls), 'PATH': f'{tmp_path}:{environ["PATH"]}'}
    for executable in ('docker', 'uv', 'uvx'):
        write_mock_executable(
            tmp_path / executable,
            f"""
            printf '{executable} %s\\n' "$*" >> "$CALLS"
            if [[ {executable} == uv && ${{1-}} == build ]]; then
                mkdir dist
                touch dist/package-1.tar.gz dist/package-1.whl
            fi
            """,
        )
    for docker_file in docker_files:
        (tmp_path / docker_file).touch()

    check_call(
        ['/usr/bin/env', 'bash', '-c', verbatim_mise_task('build'), 'build', '--pull'],
        cwd=tmp_path,
        env=environment,
    )

    assert calls.read_text().splitlines() == [
        'uv build',
        'uv publish --dry-run dist/package-1.tar.gz dist/package-1.whl',
        'uvx twine check --strict dist/package-1.tar.gz dist/package-1.whl',
        *(('docker compose --progress=plain build --pull',) if len(docker_files) == 2 else ()),
    ]


@mark.parametrize(
    ('git_output', 'output'),
    (
        ('bad path.py\\0', 'bad path.py\n'),
        ('bad\\tpath.py\\0', 'bad\tpath.py\n'),
        ('bad\\npath.py\\0', 'bad\npath.py\n'),
    ),
)
def test_no_field_separators(tmp_path: Path, git_output: str, output: str):
    task = replaced_mise_task('no-field-separators', {'git ls-files -z': f'printf "{git_output}"'})
    with raises(CalledProcessError) as error:
        check_output(['/usr/bin/env', 'bash', '-c', task], cwd=tmp_path, stderr=-1)
    assert error.value.returncode == 1
    assert error.value.output.decode().endswith(output)


def test_check_branch(tmp_path: Path):
    """Unlike tabr, this reads the branch of the dirty worktree every commit has."""
    # Arrange good name
    check_call(['git', 'init', '--quiet', '--initial-branch', 'good-name', str(tmp_path)])
    (tmp_path / 'dirty.py').write_text('dirty = 1\n')
    command = ['/usr/bin/env', 'bash', '-c', verbatim_mise_task('check-branch')]
    environment = {'GITHUB_HEAD_REF': '', 'PATH': environ['PATH']}

    # Act on good name
    check_output(command, cwd=tmp_path, env=environment, stderr=STDOUT)

    # Arrange bad name
    check_call(['git', '-C', str(tmp_path), 'switch', '--quiet', '--create', 'bad/name'])

    # Act on and assert bad name
    with raises(CalledProcessError) as error:
        check_output(command, cwd=tmp_path, env=environment, stderr=STDOUT)
    assert error.value.output == (
        b'Branch names must use lowercase letters and digits separated by single hyphens.\n'
    )

    # Arrange bad head reference
    check_call(['git', '-C', str(tmp_path), 'switch', '--quiet', '--create', 'good-name'])
    environment['GITHUB_HEAD_REF'] = 'bad/name'

    # Act on and assert bad head reference
    with raises(CalledProcessError) as error:
        check_output(command, cwd=tmp_path, env=environment, stderr=STDOUT)
    assert error.value.output == (
        b'Branch names must use lowercase letters and digits separated by single hyphens.\n'
    )


@mark.parametrize(
    'head_ref', ('Bad-name', 'bad--name', 'bad.name', 'bad_name', 'bad$(touch pwned)')
)
def test_check_branch_rejects_weird_head_references(tmp_path: Path, head_ref: str):
    command = ['/usr/bin/env', 'bash', '-c', verbatim_mise_task('check-branch')]
    environment = {'GITHUB_HEAD_REF': head_ref, 'PATH': environ['PATH']}

    with raises(CalledProcessError):
        check_output(command, cwd=tmp_path, env=environment, stderr=STDOUT)
    assert not (tmp_path / 'pwned').exists()


def test_run_on_sources(tmp_path: Path):
    """Noglob keeps brace globs literal so git pathspecs reach nested sources; -I skips binaries."""
    # Arrange
    check_call(['git', 'init', '--quiet', str(tmp_path)])
    (tmp_path / 'top.py').write_text('top = 1\n')
    (tmp_path / 'speedrun').mkdir()
    (tmp_path / 'speedrun' / '__init__.py').write_text('nested = 1\n')
    (tmp_path / 'binary.py').write_bytes(b'PK\x03\x04\x00\n')
    check_call(['git', '-C', str(tmp_path), 'add', '--all'])
    command = [
        '/usr/bin/env',
        'bash',
        '-c',
        verbatim_mise_task('run-on-sources'),
        'run-on-sources',
        'echo',
        '*.py{,i}',
    ]
    environment = {'HOME': environ['HOME'], 'PATH': environ['PATH']}

    # Act on and assert unset excludes
    with raises(CalledProcessError) as error:
        check_output(command, cwd=tmp_path, env=environment, stderr=STDOUT)
    assert 'AUTOFORMAT_EXCLUDES' in error.value.output.decode()

    # Arrange empty excludes
    environment['AUTOFORMAT_EXCLUDES'] = ''

    # Act on and assert empty excludes
    assert set(
        check_output(command, cwd=tmp_path, env=environment, stderr=DEVNULL).decode().split()
    ) == {'speedrun/__init__.py', 'top.py'}

    # Arrange top-level excludes
    environment['AUTOFORMAT_EXCLUDES'] = '^top\\.py$'

    # Act on and assert top-level excludes
    assert set(
        check_output(command, cwd=tmp_path, env=environment, stderr=DEVNULL).decode().split()
    ) == {'speedrun/__init__.py'}


def test_release(tmp_path: Path):
    calls = tmp_path / 'calls'
    environment = {'CALLS': str(calls), 'PATH': f'{tmp_path}:{environ["PATH"]}'}
    write_mock_executable(
        tmp_path / 'date',
        """
        [[ $* == '-u +v%Y.%U.' ]]
        echo v2026.34. # Sunday, August 23, 2026
        """,
    )
    write_mock_executable(tmp_path / 'gh', '''printf 'gh %s\n' "$*" >> "$CALLS"''')
    write_mock_executable(
        tmp_path / 'git',
        """
        if [[ $1 == fetch ]]; then
            printf 'git %s\n' "$*" >> "$CALLS"
        elif [[ $1 == tag ]]; then
            printf 'git %s\n' "$*" >> "$CALLS"
            echo v2026.34.08
        fi
        """,
    )

    check_call(
        ['/usr/bin/env', 'bash', '-c', verbatim_mise_task('release')], cwd=tmp_path, env=environment
    )

    assert calls.read_text().splitlines() == [
        'git fetch --tags',
        'git tag --list v2026.34.* --sort=-version:refname',
        'gh release create v2026.34.09 --generate-notes',
        'git fetch --tags',
    ]


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
    (tmp_path / '.gitignore').write_text('#\n#\n#\n')
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


def test_python_version():
    template = Path(__file__).parent / '{{cookiecutter.dot}}'
    context = {'CONA': 'speedrun', 'cookiecutter': SimpleNamespace(python_version='3.13')}
    environment = Environment(autoescape=False)  # noqa: S701
    assert "requires-python = '>=3.13'" in environment.from_string(
        (template / 'pyproject.j2.toml').read_text().split('dependencies = [', 1)[0]
    ).render(context)
    assert "target-version = 'py313'" in environment.from_string(
        (template / '.biobuddies' / 'ruff.j2.toml').read_text()
    ).render(context)
    assert '--python-version 3.13' in environment.from_string(
        (template / '.config' / 'mise.j2.toml').read_text()
    ).render({**context, 'cookiecutter': SimpleNamespace(languages='', python_version='3.13')})


@mark.parametrize(
    ('languages', 'has_rust'),
    (('Node,Python', False), ('Node,Python,Rust', True), ('node,python,rust', True)),
)
def test_rust_tool(languages: str, has_rust: bool):
    assert (
        "rust = 'stable'"
        in Environment(autoescape=False)  # noqa: S701
        .from_string(
            (Path(__file__).parent / '{{cookiecutter.dot}}' / '.config' / 'mise.j2.toml')
            .read_text()
            .split('[tools]\n', 1)[1]
        )
        .render(cookiecutter=SimpleNamespace(languages=languages))
    ) == has_rust


def test_post_gen_project_bash(tmp_path: Path):
    hook = (
        Environment(autoescape=False)  # noqa: S701
        .from_string((Path(__file__).parent / 'hooks' / 'post_gen_project.bash').read_text())
        .render(CONA='speedrun', ORGN='biobuddies', has_django=True)
    )
    (tmp_path / '.github').mkdir()
    (tmp_path / 'CONTRIBUTING.md').write_text('')
    fake_uv = tmp_path / 'uv'
    fake_uv.write_text(
        dedent("""
            #!/usr/bin/env bash
            set -o errexit -o nounset -o pipefail
            mkdir -p config
            touch manage.py
            echo "SECRET_KEY = 'django-insecure-test-key'" > config/settings.py
        """).lstrip()
    )
    fake_uv.chmod(fake_uv.stat().st_mode | stat.S_IEXEC)
    (tmp_path / 'run-post-gen.bash').write_text(hook)
    assert check_output(
        ['/usr/bin/env', 'bash', 'run-post-gen.bash'],
        cwd=tmp_path,
        env={'PATH': f'{tmp_path}:{environ["PATH"]}'},
        stderr=STDOUT,
    ).decode().splitlines()[0] == (
        '+ : CONA=speedrun ORGN=biobuddies '
        'template=hooks/post_gen_project.bash via=run-post-gen.bash'
    )
    assert (tmp_path / 'manage.py').exists()
    assert (tmp_path / 'config' / 'settings.py').read_text() == (
        "SECRET_KEY = 'django-insecure-test-key'  # noqa: typos\n"
    )
    assert not (tmp_path / 'config' / 'settings.py.bak').exists()

    for link, target in (
        ('AGENTS.md', 'CONTRIBUTING.md'),
        ('CLAUDE.md', 'CONTRIBUTING.md'),
        ('.github/copilot-instructions.md', '../CONTRIBUTING.md'),
    ):
        assert (tmp_path / link).is_symlink()
        assert (tmp_path / link).readlink() == Path(target)


def test_end_of_file_fixer():
    test_path = Path('test.sed')
    try:
        test_path.write_text('s/old/new/\n\n')
        with TemporaryDirectory() as tmpdir:
            mock_git = Path(tmpdir) / 'git'
            mock_git.write_text(f'#!/usr/bin/env bash\necho {test_path}\n')
            mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC)
            env = environ.copy()
            env['AUTOFORMAT_EXCLUDES'] = ''
            env['PATH'] = f'{tmpdir}:{env["PATH"]}'
            with raises(CalledProcessError):
                check_output(['mise', 'end-of-file-fixer'], env=env)
        assert test_path.read_text() == 's/old/new/\n'
    finally:
        test_path.unlink(missing_ok=True)
