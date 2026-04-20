#!/bin/bash
# shellcheck disable=1054,1056,1072,1073,1083
set -o errexit -o nounset -o pipefail -o xtrace
: template=hooks/post_gen_project.bash rendering=$0
{% set suffix = '{' ~ cookiecutter.languages ~ '}.gitignore' %}
# short flags for Darwin compatibility
authorization_header=${GITHUB_TOKEN:+$'\r\n'Authorization: Bearer $GITHUB_TOKEN}
curl --fail --silent --show-error \
    --header "Accept: application/vnd.github.raw+json$authorization_header" \
    https://api.github.com/repos/github/gitignore/contents/{{ suffix }} \
    | sed -E "$(cat .gitignore.sed 2>/dev/null)" >.gitignore
if [[ ! -f manage.py ]] && [[ $(sed -nE "/^dependencies = \\[[^]]*'[Dd]jango/p; /^dependencies = \\[[^]]*$/,/^]/{ /'[Dd]jango/p; }" pyproject.toml) ]]; then
    uv run --with django python -m django startproject config .
fi
ln -sf CONTRIBUTING.md AGENTS.md
ln -sf CONTRIBUTING.md CLAUDE.md
ln -sf ../CONTRIBUTING.md .github/copilot-instructions.md
