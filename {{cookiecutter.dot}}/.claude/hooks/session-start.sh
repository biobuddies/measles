#!/bin/bash
set -o errexit -o nounset -o pipefail
# Laptops already have mise and its tools installed.
[ "${CLAUDE_CODE_REMOTE:-}" = true ] || exit 0
exec "$CLAUDE_PROJECT_DIR/.biobuddies/setup.sh"
