## Pokedex

This project was started with [supopo-pai-cookiecutter-template](https://github.com/ClementPinard/supop-pai-cookiecuttter-template/tree/main)

## How to run

⚠️ Chose one of the two method below, and remove the other one.


### How to run with PySide

```bash
uv run main_qt
```

## Development

### How to run pre-commit

```bash
uvx pre-commit run -a
```

Alternatively, you can install it so that it runs before every commit :

```bash
uvx pre-commit install
```

### How to run tests

```bash
uv sync --group test
uv run pytest
```

### How to run type checking

```bash
uvx pyright numpy --pythonpath .venv/bin/python
```

### How to build docs

```bash
uv sync --group docs
cd docs && uv run make html
```

#### How to run autobuild for docs

```bash
uv sync --group docs
cd docs && make livehtml
