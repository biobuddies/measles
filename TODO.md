# TODO

## Format jinja-templated YAML

`prettier-plugin-jinja-template` formats non-jinja content as HTML, so it cannot format
jinja-wrapped YAML like
[`{{cookiecutter.dot}}/.github/workflows/act.yaml`](%7B%7Bcookiecutter.dot%7D%7D/.github/workflows/act.yaml),
which `.biobuddies/autoformat-excludes` therefore skips. Teach the plugin, or a `.j2.yaml`
parser override, to format the underlying YAML so these templates can be autoformatted.

## Improve fresh-repo bootstrap

A fresh repo should pass `mise install && mise pre-commit` immediately after generation.

- Generate `pyproject.toml` and `package.json` with project-specific values.
- Add automated regression tests for README bootstrap variants, asserting `mise install &&
  mise pre-commit` succeeds without manual file creation when running `uvx cookiecutter` in:
    - An empty directory
    - A `git init` directory with untracked files and no commits
    - A git repository with existing files and commits
- Add an automated regression test that runs `mise cookiecutter` and asserts no diff to catch
  drift between template configs and generated manifests.
