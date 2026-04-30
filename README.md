# Pico Bit

<img src="images/pico-bit.jpeg" alt="Pico Bit asset">

`pico-bit` is an MicroPython project for the Raspberry Pi Pico 2 family that:

- parses and validates DuckyScript-style payloads,
- exposes a browser-based setup mode on Wi-Fi-capable boards,
- and bundles the runtime into a single `dist/boot.py` for device deployment.

The project is inspired by Pico Ducky style workflows, but it targets MicroPython rather than CircuitPython and is organized to stay approachable for contributors.

## Intent and Scope

This repository exists to explore:

- MicroPython on Raspberry Pi Pico 2 and Pico 2 W,
- DuckyScript parsing and validation,
- USB HID keyboard behavior on RP2350 boards,
- and single-file firmware-style Python bundling for constrained targets.

The default runtime is an educational mode. It can parse a broader DuckyScript surface, but it intentionally blocks unsafe runtime features instead of executing them.

## Safety and Responsibility

This project is provided for educational and legitimate automation research purposes.

You are responsible for how you use it. If you choose to use it maliciously, that is your decision and your responsibility alone.

Always get clear authorization before automating input on any device you do not own or explicitly administer.

## Hardware Notes

- Payload mode works on Raspberry Pi Pico 2 devices that support MicroPython USB HID.
- Setup mode requires Wi-Fi access point support, so in practice you want a Raspberry Pi Pico 2 W for the web interface.
- If Wi-Fi is unavailable, payload mode can still work without the setup portal.

## Project Layout

```text
src/
  ducky/
    __init__.py
    constants.py
    errors.py
    lexer.py
    parser.py
    payload.py
    runtime.py
  hid.py
  main.py
  server.py
tests/
  ...
stubs/
  machine.pyi
  network.pyi
build.py
pyproject.toml
```

## Development Setup

This repository uses Poetry for dependency management.

1. Install Poetry.
2. Install the development environment:

```bash
poetry install
```

3. Run the checks:

```bash
poetry run pytest
poetry run pyright
poetry run ruff check .
poetry run ruff format --check .
```

4. Rebuild the deployable artifact:

```bash
poetry run python build.py
```

## Bundling

The bundler reads the local source tree, removes local imports, hoists external imports, strips docstrings and `print()` calls, and emits exactly one file:

```text
dist/boot.py
```

That file is the deployable runtime artifact for the board.

### Optional Build-Time Overrides

You can inject deployment-specific values into the generated bundle without editing source files:

```bash
poetry run python build.py \
  --ap-ssid "Studio Pico" \
  --ap-password "keyboard42" \
  --educational-mode false
```

Environment variables work too:

```bash
PICO_BIT_AP_SSID="Studio Pico" \
PICO_BIT_AP_PASSWORD="keyboard42" \
PICO_BIT_EDUCATIONAL_MODE=false \
poetry run python build.py
```

If you do not provide overrides, the defaults from `src/device_config.py` are used.

## Flashing and Running

1. Build the bundle:

```bash
poetry run python build.py
```

2. Copy `dist/boot.py` to the MicroPython filesystem as `boot.py`.
3. Place your `payload.dd` file on the board filesystem.
4. Reboot the board.

### Boot Modes

At startup, `src/main.py` reads `GP0` once:

- `GP0` held to `GND` at boot: setup mode
- `GP0` floating or high: payload mode

### Payload Mode

In payload mode the board:

1. waits for the USB HID interface to open,
2. waits a short startup delay,
3. searches for `payload.dd`,
4. validates the script,
5. and only then attempts to run it.

If parsing fails, execution is aborted.

## Setup Mode and Web Server

Setup mode is implemented in `src/server.py`.

Current defaults:

- AP name: `picoDucky`
- AP password: `88888888`
- Web UI: `http://192.168.4.1`

To change them for a specific bundle, pass `--ap-ssid` and `--ap-password` to `build.py`
or use the matching `PICO_BIT_*` environment variables.

### How to Use the Web UI

1. Hold `GP0` to `GND`.
2. Power or reset the board.
3. Connect to the access point.
4. Open `http://192.168.4.1`.
5. Edit `payload.dd` in the browser.
6. Save it or trigger a run from the page.

The web route validates the script before execution and shows parser/runtime errors in the page instead of silently ignoring them.

## Current Interpreter Shape

The DuckyScript side is split into:

- `lexer.py`: line lexing and expression tokenization
- `parser.py`: structured parsing and validation
- `runtime.py`: educational-mode execution
- `payload.py`: `payload.dd` discovery
- `errors.py`: shared exception types

## Typing and Linting

Tooling is configured in `pyproject.toml`:

- Poetry for dependencies
- Pyright for type checking
- Ruff for linting and formatting
- Pytest for tests

MicroPython-specific imports are covered by local stubs under `stubs/` so contributors do not need a machine-specific stub path.

## Testing

Host-side tests live in the top-level `tests/` directory.

They currently cover:

- lexer tokenization,
- parser validation regressions,
- runtime string expansion edge cases,
- and bundler cleanup behavior.

These tests do not replace hardware testing for real USB HID or Wi-Fi AP behavior on a Pico 2 or Pico 2 W.
