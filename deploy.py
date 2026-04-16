"""Local development configuration."""

from os import getenv
from pathlib import Path

from pyinfra import host
from pyinfra.operations import brew, files, server

home = Path(host.fact.user_home)  # pyrefly: ignore[missing-attribute]

if github_workspace := getenv('GITHUB_WORKSPACE'):
    files.link(path=str(home / 'code'), target=github_workspace)
elif not (home / 'code').exists():
    files.directory(path=str(home / 'code'))

files.line(path=str(home / '.bash_profile'), line='set -o vi')

# Terraform documentation mentions ~/.terraform.d/plugin-cache but prioritizing
# similarity to pre-commit and uv instead.
files.directory(path=str(home / '.cache/terraform'))
files.line(
    path=str(home / '.bash_profile'),
    line='TF_PLUGIN_CACHE_DIR=~/.cache/terraform; export TF_PLUGIN_CACHE_DIR',
)

if host.fact.os == 'Darwin':  # pyrefly: ignore[missing-attribute]
    # Apple stopped upgrading BASH, perhaps to avoid GPLv3, and switched to ZSH.
    # https://apple.stackexchange.com/q/371997
    files.line(
        path=str(home / '.bash_profile'),
        line='BASH_SILENCE_DEPRECATION_WARNING=1; export BASH_SILENCE_DEPRECATION_WARNING',
    )

    # https://github.com/ansible/ansible/issues/32499
    files.line(
        path=str(home / '.bash_profile'),
        line='OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES; export OBJC_DISABLE_INITIALIZE_FORK_SAFETY',
    )

    # Pre-installed on Sonoma:
    #   * Skip upgrades: host, file, less, ps
    #   * Upgrade: bash, curl, git (may come with xcode)
    brew.packages(packages=['bash', 'curl', 'fping', 'git', 'gnu-sed', 'tmux', 'tree'], update=True)

    server.shell(
        commands=[
            'defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false',
            'defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false',
            'defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false',
        ]
    )

    files.directory(path=str(home / '.config/git'))
    files.download(
        src='https://raw.githubusercontent.com/github/gitignore/master/Global/macOS.gitignore',
        dest=str(home / '.config/git/ignore'),
    )

git_configs = {
    'advice.skippedCherryPicks': 'false',  # Reduces noise when pull requests are squashed
    'core.commentChar': ';',  # Allows # hash character to be used for Markdown headers
    'diff.colormoved': 'zebra',  # Distinguishes moved lines from added and removed lines
    'init.defaultBranch': 'main',  # New standard value skips long explanation
    'pull.rebase': 'true',  # Always be rebasing
    'push.default': 'current',  # Use feature branches with "GitHub Flow"
    'rebase.autosquash': 'true',  # Act on "fixup!" and "squash!" commit title prefixes
}

for key, value in git_configs.items():
    server.shell(commands=[f'git config --global {key} "{value}"'])

# Inconsistency breaks reports like git shortlog
if name := getenv('INSH_NAME'):
    server.shell(commands=[f'git config --global user.name "{name}"'])

if email := getenv('INSH_EMAIL'):
    server.shell(commands=[f'git config --global user.email "{email}"'])
