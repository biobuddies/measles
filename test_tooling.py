"""Integration tests for tools and configuration."""

from json import loads
from os import environ, getenv
from pathlib import Path
from re import match
from subprocess import check_call, check_output

from pytest import mark


def test_mise_four_letter_abbreviations():
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


def test_prettier():
    test_path = Path('test-prettier.j2.html')
    try:
        test_path.write_text(
            '<html><body>\n{% for item in items %}<div>{{item}}</div>{% endfor %}\n</body></html>\n'
        )
        mock_git = f'git() {{ echo {test_path}; }}; export -f git;'
        check_output(['/usr/bin/env', 'bash', '-c', f'{mock_git} mise prettier-write'])
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


def test_git_ignore(tmp_path: Path):
    hook = (Path(__file__).parent / 'hooks' / 'post_gen_project.bash').read_text()
    snippet = '\n'.join(
        line for line in hook.splitlines() if 'gitignore' in line and '{%' not in line
    ).replace('{{ suffix }}', 'Python.gitignore')
    (tmp_path / '.gitignore.sed').write_text('s,^/site$,/site/ton/,\n')
    check_output(
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
        '\\n', '\n'
    )
    target = 'git describe --all --dirty --exact-match'
    assert target in original
    mocked = original.replace(target, f'echo "{git_describe}"')
    output = check_output(['/usr/bin/env', 'bash', '-c', mocked], env={}).decode().strip()
    assert output == tabr


def test_run_on_sources_excludes_binary():
    binary_path = Path('test.zip')
    try:
        binary_path.write_bytes(
            b'PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        )
        mock_git = 'git() { true; }; export -f git;'
        output = check_output(
            ['/usr/bin/env', 'bash', '-c', f'{mock_git} mise run-on-sources echo {binary_path}']
        ).decode()
        assert str(binary_path) not in output
    finally:
        binary_path.unlink(missing_ok=True)


def test_bootstrap(tmp_path: Path):
    readme = (Path(__file__).parent / 'README.md').read_text()
    bootstrap = readme.split('```bash\n')[1].split('\n```')[0]

    environment = check_output(['mise', 'envi']).decode().strip()
    tag_or_branch = check_output(['mise', 'tabr']).decode().strip()

    if environment == 'local':
        bootstrap = bootstrap.replace(
            'https://github.com/biobuddies/measles.git', f'{Path(__file__).parent}'
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

    (tmp_path / 'package.json').write_text(
        '{\n'
        '    "name": "test",\n'
        '    "devDependencies": {\n'
        '        "prettier": ">=3.8.2",\n'
        '        "prettier-plugin-jinja-template": "*",\n'
        '        "prettier-plugin-organize-attributes": "*",\n'
        '        "prettier-plugin-toml": "*"\n'
        '    }\n'
        '}\n'
    )
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\n'
        'name = "test"\n'
        'version = "0.0.1"\n'
        '\n'
        '[project.optional-dependencies]\n'
        'precommit = [\n'
        "    'actionlint-py',\n"
        "    'basedpyright',\n"
        "    'cookiecutter',\n"
        "    'django-upgrade',\n"
        "    'djlint',\n"
        "    'hadolint-py @ git+https://github.com/AleksaC/hadolint-py.git',\n"
        "    'pre-commit-hooks',\n"
        "    'pyrefly',\n"
        "    'pytest',\n"
        "    'pytest-cov',\n"
        "    'ruff',\n"
        "    'shellcheck-py',\n"
        "    'shfmt-py',\n"
        "    'typos',\n"
        "    'validate-pyproject[all]',\n"
        "    'yamllint',\n"
        ']\n'
    )

    env = {'PATH': environ['PATH']}
    check_call(
        ['/usr/bin/env', 'bash', '-c', f'set -euxo pipefail\n{bootstrap}'], cwd=tmp_path, env=env
    )
    check_call(['mise', 'trust', '--yes'], cwd=tmp_path, env=env)
    check_call(['mise', 'x', '--', 'uv', 'venv'], cwd=tmp_path, env=env)
    check_call(['mise', 'install'], cwd=tmp_path, env=env)
    check_call(['mise', 'run', 'pre-commit'], cwd=tmp_path, env=env)
