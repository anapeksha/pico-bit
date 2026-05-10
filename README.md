# Pico Bit

[![CI](https://github.com/anapeksha/pico-bit/actions/workflows/ci.yml/badge.svg)](https://github.com/anapeksha/pico-bit/actions/workflows/ci.yml)
[![Release](https://github.com/anapeksha/pico-bit/actions/workflows/release.yml/badge.svg)](https://github.com/anapeksha/pico-bit/actions/workflows/release.yml)

<img src="images/pico-bit.jpeg" alt="Pico Bit home">

`pico-bit` is an open source MicroPython project for the Raspberry Pi Pico 2 W. It combines:

- a USB HID DuckyScript runtime
- a Wi-Fi-hosted browser portal at `http://192.168.4.1`
- a lightweight staging flow for Rust agent binaries and loot collection

The Pico types payloads over USB, serves the operator portal over its access point, and can stage one uploaded agent binary on the Pico filesystem for USB-based execution.

## Features

- Boot-time and on-demand execution of `payload.dd`
- Browser editor with save and save-and-run actions
- Dry-run validation with line-level diagnostics
- Host typing target selection by OS and keyboard layout
- Binary Armory for one staged executable at a time
- USB execution stagers for Windows, Linux, and macOS
- Top-level Host USB status for the shared MSC/HID device
- Live loot updates in the portal
- Parsed loot summary plus downloadable `loot.json`

## Hardware Support

- Supported board: Raspberry Pi Pico 2 W (`RPI_PICO2_W`) only
- Use the Pico's own USB data port for HID, not a power-only carrier port

## Default Access

| What | Value |
|------|-------|
| Wi-Fi SSID | `PicoBit` |
| Wi-Fi password | `PicoBit24Net` |
| Portal URL | `http://192.168.4.1` |
| Portal username | `admin` |
| Portal password | `PicoBit24Admin` |

## Flash a Release UF2

1. Hold `BOOTSEL` while connecting the Pico.
2. Download the latest `pico-bit-RPI_PICO2_W-<version>.uf2` from the [releases page](https://github.com/anapeksha/pico-bit/releases/latest).
3. Copy it to the `RPI-RP2` drive.
4. Wait for the board to reboot.
5. Join the `PicoBit` Wi-Fi network and open `http://192.168.4.1`.

On first boot, Pico Bit creates `payload.dd` if it is missing.

## Build From Source

### Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- `mpremote` if you want to copy local builds directly to a Pico
- Rust toolchain if you want to build the agent binaries locally

Install Python dependencies:

```bash
uv sync
```

## Build the Single-File `boot.py`

This creates a bundled local artifact in `dist/boot.py` plus compiled `.mpy` files in `dist/mpy/`.

```bash
uv run python build.py
```

### Copy `boot.py` to a Pico With `mpremote`

Install `mpremote` once:

```bash
python3 -m pip install mpremote
```

Then copy the local bundle:

```bash
mpremote connect auto fs cp dist/boot.py :boot.py
mpremote connect auto reset
```

If you also want to seed a local payload file manually:

```bash
mpremote connect auto fs cp payload.dd :payload.dd
```

## Build a UF2 on Linux

Install the firmware build prerequisites:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake gcc-arm-none-eabi libnewlib-arm-none-eabi ninja-build
```

Then build the frozen firmware:

```bash
uv run python release.py build-uf2 \
  --micropython-ref v1.28.0 \
  --board RPI_PICO2_W \
  --release-version v0.0.1
```

The resulting UF2 lands in `dist/` alongside `release.json`.

## Build the Rust Agent Binaries

The Rust agents live under [`agent/`](agent/). Available binaries are:

- `recon`
- `exfil`
- `persist`
- `wipe`

### Local Development Checks

```bash
cargo check --manifest-path agent/Cargo.toml --bins
```

### Native Local Builds

Examples:

```bash
cargo build --manifest-path agent/Cargo.toml --release --bin exfil
cargo build --manifest-path agent/Cargo.toml --release --bin persist
cargo build --manifest-path agent/Cargo.toml --release --bin wipe
cargo build --manifest-path agent/Cargo.toml --release --bin recon --features with-sysinfo
```

### Linux Release-Style Builds

For Linux release-style artifacts, the project uses `cargo-zigbuild` with musl targets.

Install dependencies:

```bash
curl https://sh.rustup.rs -sSf | sh
rustup target add x86_64-unknown-linux-musl aarch64-unknown-linux-musl
python3 -m pip install ziglang
cargo install cargo-zigbuild
```

Build examples:

```bash
cargo zigbuild --manifest-path agent/Cargo.toml --release --target x86_64-unknown-linux-musl --bin exfil
cargo zigbuild --manifest-path agent/Cargo.toml --release --target x86_64-unknown-linux-musl --bin persist
cargo zigbuild --manifest-path agent/Cargo.toml --release --target x86_64-unknown-linux-musl --bin wipe
cargo zigbuild --manifest-path agent/Cargo.toml --release --target x86_64-unknown-linux-musl --bin recon --features with-sysinfo
```

For `arm64` Linux artifacts, swap the target to `aarch64-unknown-linux-musl`.

## Development Workflow

Run the standard local checks:

```bash
uv run python -c "from scripts.asset_pipeline import sync_web_assets; sync_web_assets(check=True)"
uv run ruff format --check .
uv run ruff check build.py release.py scripts src tests
uv run pyright
uv run pytest
uv run python build.py
```

## Repository Notes

- `src/web_assets.py` is generated from `web/` and should not be edited by hand
- `payload.dd` is writable on the Pico filesystem and is not frozen into firmware
- the portal stages one executable at a time as `payload.exe` for Windows agents or `payload.bin` for Linux/macOS agents
- `src/usb.py` is the source of truth for the shared `machine.USBDevice` singleton, MSC capability detection, runtime `active()` state, and staged binary filenames
- `src/keyboard.py` owns the HID keyboard runtime and keyboard layout metadata; `src/boot.py` initializes USB first, then keyboard
- release UF2 builds expose the Pico filesystem over built-in USB MSC and append the HID keyboard interface for offline agent delivery; host volume names may vary and can appear as `No Name`
- successful binary uploads activate and refresh the shared USB device so `payload.exe` or `payload.bin` is visible on the mounted Pico drive
- USB-delivered agents can write `loot-usb.json` to the Pico drive; the portal imports it into canonical `loot.json`
- the Loot panel summarizes known agent fields and keeps an icon-only `loot.json` download action
- release workflows build firmware and agent artifacts separately, then publish them together

## Releases

GitHub releases publish:

- UF2 firmware for `RPI_PICO2_W`
- prebuilt Windows, Linux, and macOS agent bundles
- `release.json` with metadata and SHA-256 checksums for published assets

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Responsible Use

Use Pico Bit only on systems you own or are explicitly authorized to test. Unauthorized access to computer systems is illegal.

## License

GPL-3.0-only. See [LICENSE](LICENSE).
