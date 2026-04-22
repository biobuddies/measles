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
```
