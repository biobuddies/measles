"""Upstream templates formatted with the shared BioBuddies configuration."""

from configparser import ConfigParser
from pathlib import Path
from subprocess import check_call, run
from tempfile import TemporaryDirectory
from tomllib import loads

from pytest import mark


def test_formatter_settings():
    root = Path(__file__).parents[1]
    editor = ConfigParser()
    editor.read_string('[DEFAULT]\n' + (root / '.editorconfig').read_text())
    djlint = loads((root / 'pyproject.toml').read_text())['tool']['djlint']
    prettier = loads((root / '.prettierrc.toml').read_text())
    ruff = loads((root / '.biobuddies/ruff.toml').read_text())
    assert djlint['indent'] == int(editor['*']['indent_size'])
    assert djlint['max_line_length'] == ruff['line-length'] == int(editor['*']['max_line_length'])
    assert djlint['quote_style'] == ruff['format']['quote-style'] == editor['*']['quote_type']
    assert prettier['singleQuote']


@mark.parametrize(
    'source',
    sorted(Path(__file__).with_name('upstream').glob('*/1-unformatted-template.*')),
    ids=lambda source: source.parent.name,
)
def test_upstream_formatting(source: Path):
    with TemporaryDirectory(dir='.') as directory:
        template = Path(directory) / source.name
        template.write_bytes(source.read_bytes())
        result = run(
            [
                'djlint',
                str(template),
                '--quiet',
                '--reformat',
                '--profile=django' if source.name.endswith('.dj.html') else '--profile=jinja',
            ],
            check=False,
        )
        assert result.returncode in (0, 1)
        check_call(['prettier', str(template), '--write'])
        assert (
            template.read_bytes()
            == source.with_name(source.name.replace('1-unformatted', '2-formatted')).read_bytes()
        )
