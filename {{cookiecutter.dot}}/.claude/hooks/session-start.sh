#!/bin/bash
set -o errexit -o nounset -o pipefail
# GitHub release downloads are firewalled in Claude Code on the web, blocking mise's aqua
# backend from fetching tenv. Build tenv from source via mise's go backend instead.
[ "${CLAUDE_CODE_REMOTE:-}" = true ] || exit 0
cd "$CLAUDE_PROJECT_DIR"
version=''
for config in .config/mise.toml mise.toml; do
    [ -f "$config" ] || continue
    version=$(sed -nE "s|^'aqua:tofuutils/tenv' = '([^']+)'.*|\1|p" "$config")
    [ -n "$version" ] && break
done
if [ -n "$version" ]; then
    export MISE_DISABLE_TOOLS=aqua:tofuutils/tenv
    echo "export MISE_DISABLE_TOOLS=$MISE_DISABLE_TOOLS" >>"$CLAUDE_ENV_FILE"
    mise use --global "go:github.com/tofuutils/tenv/v${version%%.*}/cmd/tenv@$version"
fi
mise trust --yes
mise install
mise env --shell bash >>"$CLAUDE_ENV_FILE"
