# TODO

## Improve fresh-repo bootstrap

A fresh repo should pass `mise install && mise pre-commit` immediately after generation.

- Add an automated regression test that runs the cookiecutter bootstrap and asserts
  `mise install && mise pre-commit` succeeds without manual file creation.
- Add a maintenance command to regenerate a scratch repo and show diffs to catch drift
  between template configs and generated manifests.