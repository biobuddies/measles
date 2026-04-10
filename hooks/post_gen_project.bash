#!/bin/bash
# shellcheck disable=1054,1056,1072,1073,1083
set -o errexit -o nounset -o pipefail -o xtrace
: template=hooks/post_gen_project.bash rendering=$0
{% set suffix = '{' ~ cookiecutter.languages ~ '}.gitignore' %}
# short flags for Darwin compatibility
curl -s https://raw.githubusercontent.com/github/gitignore/main/{{ suffix }} \
    | sed $([[ ! -f ./.gitignore.sed ]] || echo -Ef ./.gitignore.sed) >.gitignore
npm install --package-lock-only
uv pip compile --all-extras --output-file requirements.txt --python-platform linux pyproject.toml
git init
git add .
git commit -m 'Initial commit from measles'
