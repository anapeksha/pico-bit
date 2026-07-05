# Changelog

All notable changes to Pico Bit are documented in this file.

## v0.1.0 - 2026-07-05

### Added

- First firmware release for Raspberry Pi Pico 2 W / RP2350.
- Single-file gzipped Svelte dashboard served from embedded flash.
- Wi-Fi portal at `http://192.168.4.1`.
- USB NCM transport at `http://192.168.7.1`.
- Host HID DuckyScript execution from the saved `payload.dd` file.
- DuckyScript editor with firmware-backed save, validation, and run actions.
- Keyboard target selection for Windows, macOS, and Linux.
- Keyboard layout mapping for US, UK, German, and French layouts.
- Binary Armory with one replaceable staged binary in LittleFS.
- Armory upload/download streaming with 1 KB transfer chunks.
- 750 KB Armory binary upload limit enforced in firmware and frontend.
- NCM Armory delivery through `/api/armory` and `/api/armory/:filename`.
- Protected `payload.dd` handling: visible and downloadable on the portal, but not deletable.
- Recent run history for boot and manual execution attempts.
- Release workflow support for ELF and UF2 firmware artifacts.
- Cargo dependency caching in CI with `cargo-chef`.

### Changed

- Dashboard static assets are bundled into a single HTML artifact to avoid browser request races.
- Bootstrap is kept as a small fixed JSON snapshot; variable data is loaded from focused endpoints.
- Armory storage is constrained to a single staged binary to protect onboard flash capacity.
- Release builds keep symbol metadata required by `probe-rs`/defmt while stripping debug info.

### Fixed

- Safari dashboard loading instability caused by startup request handling.
- Browser probe handling for favicon, manifest, and related speculative requests.
- Payload deserialization and validation path for bounded no-heap firmware operation.
- Clippy and formatting issues across firmware modules.

### Release Artifacts

- `firmware-v0.1.0.elf`
- `firmware-v0.1.0.uf2`
