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
        - gunicorn
EOF
mise use --global uv@latest
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

Set environment setup script to

```bash
grep -qs 'setup\.bash' .claude/hooks/session-start.sh || measles/.config/setup.bash
```

This accommodates Claude Code on the web's different single and multiple repository startups.

TODO re-test on Codex Cloud, probably leveraging `.codex/setup.sh`

Known issue: Claude Code on the web's proxy CA lacks the key usage extension Python 3.13 requires,
so sdists downloading binaries while building, like actionlint-py and hadolint-py, fail to install;
`.config/setup.bash` skips them. https://gist.github.com/mdehling/350fc63d286a31b2653aef1362c6b0f5
