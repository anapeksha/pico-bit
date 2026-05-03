# Contributing

Thanks for helping improve `pico-bit`.

## Ground Rules

- Keep the project friendly to contributors who are new to MicroPython.
- Prefer small, reviewable changes over broad rewrites.
- Is compatible only with Raspberry Pi Pico 2 W.
- Treat parser and runtime behavior changes as user-facing changes that need tests.

## Development Setup

1. Install Poetry.
2. Install the project dependencies:

```bash
poetry install
```

## Before You Open a Change

Run the local checks:

```bash
poetry run pytest
poetry run pyright
poetry run ruff check build.py deploy.py scripts src tests
poetry run ruff format --check .
poetry run python3 build.py
```

For board-specific bundles, you can also use:

```bash
poetry run python3 build.py --ap-ssid "Lab Pico" --ap-password "keyboard42"
```

If you intentionally change formatting, run:

```bash
poetry run ruff format .
```

## Code Organization

- Put DuckyScript parsing work in `src/ducky/lexer.py` and `src/ducky/parser.py`.
- Put runtime execution behavior in `src/ducky/runtime.py`.
- Keep hardware-facing code in `src/hid.py`, `src/main.py`, and `src/server.py`.
- Keep host-side tests in the top-level `tests/` directory.

## Tests

Please add or update tests when you change:

- lexer tokenization,
- parser validation rules,
- runtime command behavior,
- payload discovery,
- or bundler output behavior.

## Bundled Output

`dist/boot.py` should be built using `build.py`.
`pico-bit-RPI_PICO2_W-v0.0.1.uf2` should be built using `deploy.py`

When source changes affect the deployable runtime, rebuild it with:

```bash
poetry run python3 build.py
```

```bash
poetry run python3 deploy.py build-uf2 --micropython-ref v1.28.0 --board RPI_PICO2_W --release-version 0.0.1
```

## Documentation

Update `README.md` when you change:

- setup mode behavior,
- required hardware assumptions,
- or deployment steps.

## Security and Responsible Use

This repository is for legitimate automation research, learning, and hardware experimentation.

Do not submit changes that assume or encourage unauthorized use on systems you do not own or administer.
