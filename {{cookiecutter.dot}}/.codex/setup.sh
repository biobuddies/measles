#!/bin/bash
set -o errexit -o nounset -o pipefail
cd "$(git rev-parse --show-toplevel)"
mise trust --yes
mise install
printf "eval \"\$(mise activate bash)\"\n" >>~/.bashrc
