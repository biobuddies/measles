"""Integration tests for tools and configuration."""

from json import loads
from os import environ, getenv
from pathlib import Path
from re import match
from subprocess import check_output

from pytest import mark


def test_mise():
    assert check_output(['mise', 'cona']) == b'measles\n'

    assert check_output(['mise', 'envi']) == b'github\n' if getenv('GITHUB_ACTIONS') else b'local\n'

    giha = check_output(['mise', 'giha'])
    assert match(rb'^[0-9a-f]{40}(-dirty)?\n$', giha)
    is_dirty = bool(check_output(['git', 'status', '--porcelain', '--untracked-files=no']))
    assert giha.endswith(b'-dirty\n') == is_dirty

    assert check_output(['mise', 'orgn']) == b'biobuddies\n'

    tabr_env = {
        'MISE_TRUSTED_CONFIG_PATHS': getenv('MISE_TRUSTED_CONFIG_PATHS', ''),
        'PATH': environ['PATH'],
    }
    assert check_output(['mise', 'tabr'], env=tabr_env) == (
        b''
        if is_dirty
        else check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip() + b'\n'
    )


def test_prettier():
    test_path = Path('test-prettier.j2.html')
    try:
        test_path.write_text(
            '<html><body>\n{% for item in items %}<div>{{item}}</div>{% endfor %}\n</body></html>\n'
        )
        check_output(['mise', 'prettier-write'])
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
        check_output(['mise', 'typos', str(input_path)])  # noqa: S603
        assert output_path.read_text() == 'experiment:\n  - \u03bc\n  yaml\n'
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_git_ignore(tmp_path: Path):
    hook = (Path(__file__).parent / 'hooks' / 'post_gen_project.bash').read_text()
    snippet = '\n'.join(
        line for line in hook.splitlines() if 'gitignore' in line and '{%' not in line
    ).replace('{{ suffix }}', 'Python.gitignore')
    (tmp_path / '.gitignore.sed').write_text('s,^/site$,/site/ton/,\n')
    check_output(  # noqa: S603
        [
            '/usr/bin/env',
            'bash',
            '-c',
            'set -o errexit -o nounset -o pipefail; curl(){ echo /site; }; ' + snippet,
        ],
        cwd=tmp_path,
        env={},
    )
    assert (tmp_path / '.gitignore').read_text() == '/site/ton/\n'


@mark.parametrize(
    ('git_describe', 'tabr'),
    (
        ('remotes/origin/mybranch', 'mybranch'),
        ('heads/mybranch', 'mybranch'),
        ('tags/v2025.02.03', 'v2025.02.03'),
        ('heads/mybranch-dirty', ''),
    ),
)
def test_tabr_git_describe_mocked(git_describe: str, tabr: str):
    original = loads(check_output(['mise', 'tasks', 'info', 'tabr', '--json']))['run'][0].replace(
        '\n', '\n'
    )
    target = 'git describe --all --dirty --exact-match'
    assert target in original
    mocked = original.replace(target, f'echo "{git_describe}"')
    output = (
        check_output(  # noqa: S603
            ['/usr/bin/env', 'bash', '-c', mocked], env={}
        )
        .decode()
        .strip()
    )
    assert output == tabr
