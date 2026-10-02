#!/bin/bash
# Bootstrap mise and this repository's tools in agent sandboxes lacking both. Hosts discard
# session start hook output, so append everything to a log reviewable afterwards.
set -o errexit -o nounset -o pipefail -o xtrace
log=/tmp/setup.log
exec > >(tee -a "$log") 2>&1
datetimez() { date -u '+%F %TZ'; }
trap 'echo "ERROR $(datetimez) $PWD"' ERR
toplevel=$(git -C "$(dirname "${BASH_SOURCE[0]:?requires BASH}")" rev-parse --show-toplevel)
cd "$toplevel"
echo "Start $(datetimez) $PWD"
# See also mise check-branch and CONTRIBUTING.md
branch=$(git branch --show-current)
[[ $branch == "${branch##*/}" ]] || git branch --move "${branch##*/}"
export PATH="$HOME/.local/bin:$PATH"
command -v mise >/dev/null || curl https://mise.run | sh
# Trust the parent so sibling checkouts of a multi-repository session need no second visit.
mise settings add trusted_config_paths "$(dirname "$toplevel")"
mise trust --yes
mise install
# mise install exits 0 when postinstall fails
# dup .config/mise.toml tasks.actionlint
proxy_ca=/root/.ccr/agent-proxy-ca.crt
if [[ -f $proxy_ca ]] \
    && ! openssl x509 -in $proxy_ca -noout -ext keyUsage 2>/dev/null | grep -q 'Key Usage'; then
    # Proxy CA breaks their sdist builds; see measles README.md Known issue
    grep -vE '^(actionlint|hadolint)-py' requirements.txt | mise exec -- uv pip sync -
else
    mise exec -- uv pip sync requirements.txt
fi
mise exec -- npm clean-install --no-audit --no-fund
# Claude Code sources this file before each Bash tool command, activating mise for that directory
[ -z "${CLAUDE_ENV_FILE-}" ] || mise activate bash >>"$CLAUDE_ENV_FILE"
if [ "${CLAUDE_CODE_REMOTE:-}" = true ]; then
    mkdir --parents ~/.claude
    ln --force --symbolic "$toplevel/.claude/settings.json" ~/.claude/settings.json
fi
echo "Complete $(datetimez) $PWD"
