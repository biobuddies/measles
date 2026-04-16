# Measles

Continuous [cookiecutter](https://github.com/cookiecutter/cookiecutter) featuring
[mise](https://github.com/jdx/mise).

## Bootstrap

```bash
printf '%s\n' 'default_context:' '    languages: Node,Python' > .cookiecutter.yaml
mise use python@3.12 uv@latest
uvx cookiecutter --no-input --overwrite-if-exists https://github.com/biobuddies/measles.git
```

Fresh repos should pass `mise install && mise precommit` immediately after generation.