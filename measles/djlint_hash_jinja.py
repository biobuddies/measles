"""Run djlint on hash Jinja through curly Jinja copies, writing reformatting back as hash Jinja."""

from os.path import relpath
from pathlib import Path
from re import escape, sub
from subprocess import run
from sys import argv
from tempfile import TemporaryDirectory

# Hash tags become curly tags; literal curly braces, such as GitHub ${{ }}, hide in private use
# characters so the way back is unambiguous
curly = {
    '#%': '{%',
    '%#': '%}',
    '#*': '{#',
    '*#': '#}',
    '#{': '{{',
    '}#': '}}',
    '{%': '',
    '%}': '',
    '{#': '',
    '#}': '',
    '{{': '',
    '}}': '',
}
hashed = {value: key for key, value in curly.items()}


def translate(source: str, mapping: dict[str, str]) -> str:
    """Replace every mapping key in one left-to-right pass, so replacements never chain."""
    return sub('|'.join(map(escape, mapping)), lambda match: mapping[match[0]], source)


def main(arguments: list[str]) -> int:
    """Pass flags to djlint; translate path arguments to temporary curly copies and back."""
    paths = [Path(argument) for argument in arguments if Path(argument).is_file()]
    flags = [argument for argument in arguments if not Path(argument).is_file()]
    with TemporaryDirectory(dir='.') as directory:
        copies = [Path(directory, str(index), path.name) for index, path in enumerate(paths)]
        for path, copy in zip(paths, copies, strict=True):
            copy.parent.mkdir()
            copy.write_text(translate(path.read_text(), curly))
        result = run(  # noqa: S603 arguments come from mise tasks
            ['djlint', *flags, *map(str, copies)], capture_output=True, check=False, text=True
        )
        output = translate(result.stdout, hashed)
        for path, copy in zip(paths, copies, strict=True):
            if (source := translate(copy.read_text(), hashed)) != path.read_text():
                path.write_text(source)
            output = output.replace(relpath(copy), str(path))
    print(output, end='')  # noqa: T201 relay djlint output
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main(argv[1:]))
