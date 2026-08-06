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
uvx cookiecutter --no-input --overwrite-if-exists https://github.com/biobuddies/measles.git
mise trust --yes
mise install
mise pre-commit-all
mise test
```

## Agent sandboxes

`.biobuddies/setup.sh` installs mise and the tools of the repository containing it, appending to
`/tmp/setup.log`. Codex Cloud runs it through `.codex/setup.sh`; Claude Code on the web runs it
through the `.claude/hooks/session-start.sh` SessionStart hook, once per source repository, but
only while snapshotting the environment. Repositories added later, or lacking `.claude`, need the
environment setup script to cover them:

```bash
for setup in ~/*/.biobuddies/setup.sh; do "$setup"; done
```
