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
version=''
for config in .config/mise.toml mise.toml; do
    [ -f "$config" ] || continue
    version=$(sed -nE "s|^'aqua:tofuutils/tenv' = '([^']+)'.*|\1|p" "$config")
    [ -n "$version" ] && break
done
# GitHub release downloads are firewalled in Claude Code on the web, blocking mise's aqua
# backend from fetching tenv. Build tenv from source via mise's go backend instead.
if [ -n "$version" ] && [ "${CLAUDE_CODE_REMOTE:-}" = true ]; then
    mise settings add disable_tools aqua:tofuutils/tenv
    mise use --global "go:github.com/tofuutils/tenv/v${version%%.*}/cmd/tenv@$version"
fi
mise install
# mise install exits 0 when postinstall fails
if [ "${CLAUDE_CODE_REMOTE:-}" = true ]; then
    # Proxy CA breaks their sdist builds; see measles README.md Known issue
    grep -vE '^(actionlint|hadolint)-py' requirements.txt | mise exec -- uv pip sync -
else
    mise exec -- uv pip sync requirements.txt
fi
mise exec -- npm clean-install --no-audit --no-fund
if [ "${CLAUDE_CODE_REMOTE:-}" = true ]; then
    mkdir --parents ~/.claude
    ln --force --symbolic "$toplevel/.claude/settings.json" ~/.claude/settings.json
fi
# Multi-repository sessions start in the parent directory, so activate per directory instead of
# exporting one repository's paths.
# shellcheck disable=SC2016
grep -q 'mise activate' ~/.bashrc || echo 'eval "$(mise activate bash)"' >>~/.bashrc
echo "Complete $(datetimez) $PWD"
