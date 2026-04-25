#!/bin/bash
# shellcheck disable=1054,1056,1072,1073,1083
set -o errexit -o nounset -o pipefail -o xtrace
: template=hooks/post_gen_project.bash via="$0"
if [[ ! -f manage.py ]] && [[ $(
    sed -nE "
        /^dependencies = \\[[^]]*'[Dd]jango/p
        /^dependencies = \\[[^]]*$/,/^]/{ /'[Dd]jango/p; }
    " pyproject.toml
) ]]; then
    uv run --with django python -m django startproject config .
fi
ln -sf CONTRIBUTING.md AGENTS.md
ln -sf CONTRIBUTING.md CLAUDE.md
ln -sf ../CONTRIBUTING.md .github/copilot-instructions.md
