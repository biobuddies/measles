#!/bin/bash
# shellcheck disable=1054,1056,1072,1073,1083
set -o errexit -o nounset -o pipefail -o xtrace
: template=hooks/post_gen_project.bash via="$0"
# shellcheck disable=SC1009
{% if has_django -%}
[[ -f manage.py ]] || uv run --with django python -m django startproject config .
{% endif -%}
# https://developers.openai.com/codex/guides/agents-md
# https://forgecode.dev/docs/custom-rules/
ln -sf CONTRIBUTING.md AGENTS.md
# https://code.claude.com/docs/en/best-practices#write-an-effective-claude-md
ln -sf CONTRIBUTING.md CLAUDE.md
# TODO test removal
ln -sf ../CONTRIBUTING.md .github/copilot-instructions.md
# Supporting multiple files:
# https://code.visualstudio.com/docs/copilot/customization/custom-instructions
# https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
# https://zed.dev/docs/ai/rules
