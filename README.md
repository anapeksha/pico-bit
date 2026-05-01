# Pico Bit

<img src="images/pico-bit.jpeg" alt="Pico Bit home">

`pico-bit` is a MicroPython DuckyScript interpreter for the Raspberry Pi Pico 2 family. It validates and runs `payload.dd`, can expose a browser-based setup portal on Wi-Fi-capable boards, and bundles the whole runtime into a single `dist/boot.py`.

The project is meant to be approachable for MicroPython users and contributors who want a Pico Ducky style workflow without switching to CircuitPython.

## Purpose

This repository focuses on:

- DuckyScript parsing and validation on MicroPython
- USB HID keyboard behavior on RP2350 boards
- Wi-Fi payload editing on Pico 2 W hardware
- single-file bundling for constrained embedded targets

By default, the runtime stays in a safe mode. It can parse a broader DuckyScript surface, but unsafe runtime features remain blocked unless `ALLOW_UNSAFE` is enabled.

## Responsibility

This project is for legitimate automation, learning, and hardware experimentation.

You are responsible for how you use it. If you choose to use it maliciously, that is your decision and your responsibility alone.

Only run payloads on systems you own or are explicitly authorized to administer.

## Hardware

- Payload mode works on Raspberry Pi Pico 2 devices that support MicroPython USB HID.
- Setup mode requires Wi-Fi AP support, so you typically want a Raspberry Pi Pico 2 W.
- On carrier boards that expose multiple USB ports, use the Pico's own USB data port for HID.

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
  device_config.py
  hid.py
  main.py
  server.py
  status_led.py
tests/
stubs/
build.py
pyproject.toml
```

## Development

This repository uses Poetry.

```bash
poetry install
poetry run pytest
poetry run pyright
poetry run ruff check .
poetry run ruff format --check .
poetry run python3 build.py
```

## Bundling

The bundler reads `src/`, removes local imports, hoists external imports, strips docstrings and `print()` calls, and emits exactly one deployable file:

```text
dist/boot.py
```

## Build-Time Configuration

You can override the setup AP and runtime safety mode without editing source files:

```bash
poetry run python3 build.py \
  --ap-ssid "Studio Pico" \
  --ap-password "keyboard42" \
  --allow-unsafe true
```

Environment variables work too:

```bash
PICO_BIT_AP_SSID="Studio Pico" \
PICO_BIT_AP_PASSWORD="keyboard42" \
PICO_BIT_ALLOW_UNSAFE=true \
poetry run python3 build.py
```

Defaults are defined in `src/device_config.py`.

## Flashing

1. Build the bundle with `poetry run python3 build.py`.
2. Copy `dist/boot.py` to the MicroPython filesystem as `boot.py`.
3. Copy `payload.dd` to the board filesystem.
4. Reboot the board.

## Boot Modes

`src/main.py` checks `GP22` once at startup:

- `GP22` held to `GND`: setup mode
- `GP22` floating or high: payload mode

## Payload Mode

In payload mode the board:

1. initializes USB HID
2. waits for the host to enumerate the keyboard
3. searches for `payload.dd`
4. validates the script
5. runs it only if parsing succeeds

Parse failures stop execution before runtime.

## Setup Mode

Setup mode starts the web server in `src/server.py`.

Current defaults:

- AP name: `picoBit`
- AP password: `88888888`
- Web UI: `http://192.168.4.1`

To use it:

1. Hold `GP22` to `GND`.
2. Power-cycle or reset the board.
3. Join the access point.
4. Open `http://192.168.4.1`.
5. Edit `payload.dd` in the browser.
6. Save it or run it from the page.

The web UI validates the script before execution and reports parser or runtime errors in the page.

## Runtime Safety

`ALLOW_UNSAFE` is `False` by default.

That means:

- the parser can still understand a broader DuckyScript surface
- higher-risk runtime features stay blocked
- blocked features fail clearly instead of running silently

If you set `ALLOW_UNSAFE=True` at build time, the runtime will execute its supported unsafe paths too.

## Testing

Host-side tests live in `tests/`.

They cover:

- lexer behavior
- parser validation
- runtime string expansion
- AP startup fallbacks
- bundler output

These tests do not replace real hardware validation for USB HID or Wi-Fi behavior on a Pico 2 or Pico 2 W.

## License

This project is licensed under GPL-3.0-only. See `LICENSE`.
