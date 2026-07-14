# Pico Bit

[![Validate](https://github.com/anapeksha/pico-bit/actions/workflows/validate.yml/badge.svg)](https://github.com/anapeksha/pico-bit/actions/workflows/validate.yml)
[![Release](https://github.com/anapeksha/pico-bit/actions/workflows/release.yml/badge.svg)](https://github.com/anapeksha/pico-bit/actions/workflows/release.yml)

> **WARNING:** This software is strictly for authorized educational and security testing purposes; any unauthorized use or deployment is entirely at your own risk and liability.

<img src="images/pico-bit.jpeg" alt="Pico Bit home">

`pico-bit` is an open source Rust Embassy firmware for the Raspberry Pi Pico 2 W. It combines a USB Host HID DuckyScript runtime, USB NCM file delivery, LittleFS-backed storage, and a Wi-Fi-hosted dashboard for authorized security research, lab automation, and defensive validation.

Current release: `v0.1.3`

## What Works

- Single-file dashboard served at `http://192.168.4.1`
- Boot-time and on-demand execution of the saved `payload.dd`
- Browser editor with firmware-backed save, validation, and run actions
- Host typing target selection by operating system and keyboard layout
- Host HID and NCM link state surfaced in the dashboard
- Binary Armory upload, download, copy-link, and delete operations over LittleFS
- Protected `payload.dd` file: visible in the file table, downloadable, but not deletable
- Recent boot/manual run history for the current boot session
- Single replaceable Armory binary with a 750 KB upload limit enforced in both frontend and firmware
- On-board status LED patterns for boot, network, HID, payload, Armory, and error states
- Single gzipped Svelte 5 + Tailwind v4 dashboard artifact embedded into firmware flash
- `cargo-embed` as the default local flash, RTT, and debug toolchain
- Release workflow that builds and attaches `firmware-{version tag}.uf2` and `firmware-{version tag}.elf`

## Hardware

- Supported board: Raspberry Pi Pico 2 W (`RPI_PICO2_W`)
- Firmware target: `thumbv8m.main-none-eabihf`
- The Pico USB data port provides Host HID and USB NCM transport.
- The Wi-Fi dashboard is exposed through the Pico AP.
- The status LED uses the Pico 2 W on-board LED through the CYW43 controller.

## Default Access

| What | Value |
|------|-------|
| Wi-Fi SSID | `PicoBit` |
| Wi-Fi password | `PicoBit24Net` |
| Dashboard URL | `http://192.168.4.1` |
| NCM file root | `http://192.168.7.1` |
| NCM staged binary | `http://192.168.7.1/api/armory/payload.bin` |

The dashboard has no portal login in `v0.1.3`. AP credentials are firmware build-time values.

## Dashboard Scope

The UI is intentionally small and operational:

- Top status cards show AP details, Host HID readiness, and NCM link state.
- The DuckyScript editor edits the single `payload.dd` file.
- Save validates and writes the editor text to LittleFS.
- Run saves the current editor text first, then triggers Host HID execution.
- Validation failures open the validation modal and do not trigger execution.
- Binary Armory lists `payload.dd` and the single staged binary, supports upload/download/copy-link/delete, and blocks deletion of `payload.dd`.
- Layout controls update the firmware keyboard target immediately.
- Recent runs show compact current-session run metadata.

## API Surface

The frontend uses only these endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/bootstrap` | Fixed startup state: AP, Host HID, NCM, keyboard target, seeded flag |
| `GET` | `/api/armory` | Bounded LittleFS file listing |
| `POST` | `/api/armory/upload` | Stream upload to `/armory/payload.bin`, replacing any existing Armory binary |
| `GET` | `/api/armory/:filename` | Stream file download |
| `DELETE` | `/api/armory/:filename` | Delete Armory file, except `payload.dd` |
| `GET` | `/api/payload` | Read current `payload.dd` |
| `POST` | `/api/payload` | Validate and overwrite `payload.dd` |
| `POST` | `/api/payload/run` | Validate saved `payload.dd` and trigger Host HID execution |
| `POST` | `/api/keyboard/layout` | Update keyboard OS/layout codes |
| `GET` | `/api/runs` | Current-session run history |

There is no status API, auth API, login/logout route, or browser-storage startup restore flow in `v0.1.3`.
The NCM surface exposes only the Armory list and staged binary download; `payload.dd` downloads remain portal-only.

## Storage Model

- LittleFS is mounted at boot.
- `/armory` is created automatically.
- `payload.dd` is created automatically if missing.
- The editor always overwrites `payload.dd`.
- Armory stores one replaceable binary at `/armory/payload.bin`; a new upload removes previous Armory files, opens `payload.bin` once, then writes request chunks.
- File listings are bounded and serialized without heap allocation.

## Limits

| Limit | Value |
|-------|-------|
| Payload editor buffer | 2 KB |
| Armory upload limit | 750 KB |
| Armory upload stream chunk | 4 KB |
| Armory download stream chunk | 1 KB |
| Run history | 6 entries |
| Dashboard artifact | `dist/index.html.gz` |

### Status LED

| State | Pattern |
|-------|---------|
| `boot` | 3 x 80 ms on / 80 ms off |
| `setup_entered` | 6 x 400 ms on / 200 ms off |
| `setup_ap_starting` | 1 x 180 ms on / 120 ms off, 250 ms gap |
| `setup_ap_ready` | 1 x 700 ms on |
| `setup_server_ready` | 2 x 220 ms on / 140 ms off |
| `hid_constructed` | 1 x 350 ms on / 250 ms off, 600 ms gap |
| `usb_enumerated` | 3 x 350 ms on / 250 ms off, 600 ms gap |
| `payload_entered` | 2 x 350 ms on / 250 ms off, 600 ms gap |
| `payload_ready` | 4 x 350 ms on / 250 ms off, 600 ms gap |
| `payload_running` | 3 x 120 ms on / 90 ms off, 180 ms gap |
| `payload_complete` | 2 x 500 ms on / 300 ms off |
| `binary_injecting` | 4 x 90 ms on / 70 ms off, 160 ms gap |
| `binary_inject_failed` | 5 x 90 ms on / 70 ms off, 260 ms gap |
| `keyboard_layout_changed` | 3 x 80 ms on / 80 ms off, 220 ms gap |
| `loot_imported` | 3 x 180 ms on / 80 ms off, 120 ms gap |
| `usb_agent_mounted` | 2 x 80 ms on / 80 ms off, 120 ms gap |
| `usb_enum_timeout` | 1 x 80 ms on / 80 ms off |
| `script_error` | 4 x 350 ms on / 250 ms off, 1500 ms gap |
| `payload_read_failed` | 5 x 350 ms on / 250 ms off, 1500 ms gap |
| `payload_find_failed` | 6 x 350 ms on / 250 ms off, 1500 ms gap |
| `setup_ap_failed` | 7 x 350 ms on / 250 ms off, 1500 ms gap |
| `setup_server_failed` | 8 x 350 ms on / 250 ms off, 1500 ms gap |
| `payload_missing` | 10 x 350 ms on / 250 ms off, 1500 ms gap |

## Build

Build the embedded dashboard first, then build/check firmware:

```sh
npm ci --prefix web
npm --prefix web run build
cargo check --target thumbv8m.main-none-eabihf
```

Install the local flash/debug tool once:

```sh
cargo install cargo-embed --locked
```

Flash and run on a connected RP2350 board. The project `cargo run` path now routes directly through [`Embed.toml`](/Users/anapeksha/Documents/Projects/pico-bit/Embed.toml:1) and opens the default RTT session through `cargo-embed`:

```sh
cargo run
```

Open the GDB server profile:

```sh
cargo embed gdb
```

Build release firmware:

```sh
npm --prefix web run build
cargo build --release --target thumbv8m.main-none-eabihf
cp target/thumbv8m.main-none-eabihf/release/pico-bit firmware-v0.1.3.elf
elf2uf2-rs firmware-v0.1.3.elf firmware-v0.1.3.uf2
```

## Verification

Frontend gates:

```sh
npm --prefix web run check
npm --prefix web run lint
npm --prefix web test -- --run
npm --prefix web run build
```

Firmware gates:

```sh
cargo fmt --all -- --check
cargo check --target thumbv8m.main-none-eabihf
cargo clippy --target thumbv8m.main-none-eabihf --no-deps -- -D warnings -A clippy::new_without_default
cargo build --release --target thumbv8m.main-none-eabihf
```

Host-side tests for firmware-agnostic modules:

```sh
cargo test --lib --no-default-features --target x86_64-unknown-linux-gnu
```

On macOS without a Linux cross-linker, use the native host target for local testing:

```sh
cargo test --lib --no-default-features --target aarch64-apple-darwin
```

For local hardware smoke testing with the committed `cargo-embed` configuration:

```sh
cargo run
```

## Release

The release workflow runs when a GitHub release is published with a tag matching:

```text
v*.*.*
```

For `v0.1.3`, publish a GitHub release tagged:

```text
v0.1.3
```

The workflow builds the web dashboard, compiles release firmware, converts the ELF to UF2, uploads a workflow artifact, and attaches:

- `firmware-v0.1.3.uf2`
- `firmware-v0.1.3.elf`

## Current Completion State

`v0.1.3` is complete for the current UI scope. All frontend API calls are backed by firmware handlers, and the remaining dynamic dashboard state is sourced from runtime state or LittleFS.
