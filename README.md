# Measles

Continuous [cookiecutter](https://github.com/cookiecutter/cookiecutter) featuring
[mise](https://github.com/jdx/mise).

## Bootstrap

```bash
cat <<'EOF' > .cookiecutter.yaml
default_context:
    languages: Node,Python
    python_dependencies:
        - django
EOF
mise use uv@latest
uvx cookiecutter --config-file .cookiecutter.yaml --no-input --overwrite-if-exists https://github.com/biobuddies/measles.git
mise trust --yes
mise install
mise pre-commit-all
mise test
```

## Autoformat excludes

To exclude files from autoformatting and linting, add extended regular expressions
for relative paths from the repository root to `.config/autoformat-excludes` like:

```
^public/bundle\.min\.js$
^publickey\.asc$
```

## Agent sandboxes

`.biobuddies/setup.bash` installs mise and the tools of the repository containing it, appending to
`/tmp/setup.log`. Codex Cloud runs it through `.codex/setup.sh`; Claude Code on the web runs it
through the `.claude/hooks/session-start.sh` SessionStart hook, once per source repository, but
only while snapshotting the environment. Repositories added later, or lacking `.claude`, need the
environment setup script to source it.

Trusting the parent directory lets `mise activate` supply each sibling's environment on `cd`, so
one run covers a multi-repository session. Installing tools stays explicit, because entering a
directory installs nothing: run `mise install` in whichever sibling gets a feature branch.
