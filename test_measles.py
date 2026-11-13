"""Test the Measles Cookiecutter extension."""

from collections.abc import Callable
from os import environ
from pathlib import Path
from subprocess import check_call

from pytest import CaptureFixture, MonkeyPatch, fixture, raises

import measles
from measles.djlint_hash_jinja import curly, hashed, main, translate

MISSING = object()


@fixture
def precise_environment(monkeypatch: MonkeyPatch) -> Callable[..., None]:
    def inner(**kwargs: str) -> None:
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
            | {'PWD': str(Path.cwd()), **kwargs}
        ).items():
            if value is MISSING:
                monkeypatch.delitem(environ, key, raising=False)
            else:
                monkeypatch.setenv(key, value)  # pyrefly: ignore[bad-argument-type]

        monkeypatch.setattr(measles, 'PWD', Path(environ['PWD']))

    return inner


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
        measles, 'check_output', lambda *_, **__: b'https://github.com/biobuddies/wriggle.git\n'
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
        measles, 'check_output', lambda *_, **__: b'git@github.com:biobuddies/wriggle.git\n'
    )

    assert measles.cona() == 'wriggle'


def test_cona_orgn_follow_pwd_out_of_template(
    monkeypatch: MonkeyPatch, tmp_path: Path, precise_environment: Callable[..., None]
):
    for name, remote in (('template', 'measles'), ('downstream', 'wriggle')):
        check_call(['git', 'init', '--quiet', tmp_path / name])
        check_call([
            'git',
            '-C',
            tmp_path / name,
            'remote',
            'add',
            'origin',
            f'https://github.com/biobuddies/{remote}.git',
        ])
    monkeypatch.chdir(tmp_path / 'template')
    precise_environment(PWD=str(tmp_path / 'downstream'))
    monkeypatch.setenv('PWD', str(tmp_path / 'template'))

    assert (measles.cona(), measles.orgn()) == ('wriggle', 'biobuddies')


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
        measles, 'check_output', lambda *_, **__: b'git@github.com:biobuddies/wriggle.git\n'
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


def test_djlint_hash_jinja(capsys: CaptureFixture[str], tmp_path: Path):
    workflow = Path('{{cookiecutter.dot}}/.github/workflows/act.hj.yaml')
    assert translate(translate(workflow.read_text(), curly), hashed) == workflow.read_text()
    assert main(['--lint', '--profile=jinja', str(workflow)]) == 0
    capsys.readouterr()
    crowded = tmp_path / 'crowded.hj.yaml'
    crowded.write_text('name: #{cookiecutter.name}#\n')
    assert main(['--lint', '--profile=jinja', str(crowded)]) == 1
    output = capsys.readouterr().out
    assert str(crowded) in output
    assert 'T001' in output
    assert crowded.read_text() == 'name: #{cookiecutter.name}#\n'
