# TODO

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
