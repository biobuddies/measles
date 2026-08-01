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
def test_cookiecutter(tmp_path: Path, case: tuple[str, dict[str, str], str, list[str], str]):
    codename, environment, branch, arguments, expected = case
    # Not running mise directly because .venv/bin/cookiecutter is tricky to stub
    task = loads(check_output(['mise', 'tasks', 'info', 'cookiecutter', '--json']))['run'][0]
    task = task.replace('\\n', '\n').replace('tabr=$(mise tabr)', f'tabr={branch}')
    mock_cookiecutter = tmp_path / 'cookiecutter'
    mock_cookiecutter.write_text('#!/usr/bin/env echo\n')
    mock_cookiecutter.chmod(mock_cookiecutter.stat().st_mode | stat.S_IEXEC)

    output = (
        check_output(
            ['/usr/bin/env', 'bash', '-c', task, 'cookiecutter', *arguments],
            env={
                'CONA': codename,
                'HOME': '/home/biobuddy',
                'ORGN': 'biobuddies',
                'PATH': f'{tmp_path}:{environ["PATH"]}',
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


def test_run_on_sources(tmp_path: Path):
    """Noglob keeps brace globs literal so git pathspecs reach nested sources; -I skips binaries."""
    script = loads(check_output(['mise', 'tasks', 'info', 'run-on-sources', '--json']))['run'][
        0
    ].replace('\\n', '\n')
    check_call(['git', 'init', '--quiet', str(tmp_path)])
    (tmp_path / '.biobuddies').mkdir()
    (tmp_path / '.biobuddies' / 'autoformat-excludes').write_text('')
    (tmp_path / 'top.py').write_text('top = 1\n')
    (tmp_path / 'speedrun').mkdir()
    (tmp_path / 'speedrun' / '__init__.py').write_text('nested = 1\n')
    (tmp_path / 'binary.py').write_bytes(b'PK\x03\x04\x00\n')
    check_call(['git', '-C', str(tmp_path), 'add', '--all'])
    sources = (
        check_output(
            ['/usr/bin/env', 'bash', '-c', script, 'bash', 'echo', '*.py{,i}'],
            cwd=tmp_path,
            env={'HOME': environ['HOME'], 'PATH': environ['PATH']},
            stderr=DEVNULL,
        )
        .decode()
        .split()
    )
    assert set(sources) == {'speedrun/__init__.py', 'top.py'}


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


def test_post_gen_project_bash(tmp_path: Path):
    hook = (
        Environment(autoescape=False)  # noqa: S701
        .from_string((Path(__file__).parent / 'hooks' / 'post_gen_project.bash').read_text())
        .render(CONA='speedrun', ORGN='biobuddies', has_django=True)
    )
    (tmp_path / '.github' / 'workflows').mkdir(parents=True)
    (tmp_path / '.github' / 'workflows' / 'act.j2.yaml').write_text('name: act\n')
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
    assert not (tmp_path / '.github' / 'workflows' / 'act.j2.yaml').exists()
    assert (tmp_path / '.github' / 'workflows' / 'act.yaml').read_text() == 'name: act\n'

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
            env['PATH'] = f'{tmpdir}:{env["PATH"]}'
            with raises(CalledProcessError):
                check_output(['mise', 'end-of-file-fixer'], env=env)
        assert test_path.read_text() == 's/old/new/\n'
    finally:
        test_path.unlink(missing_ok=True)
