# Changelog

All notable changes to Pico Bit are documented in this file.

## v0.1.1 - 2026-07-06

### Added

- WS2812 RGB status LED driver for GP16 using PIO1 and DMA channel 2.
- Queued, non-blocking LED status events for boot, Wi-Fi bring-up, USB NCM, Host HID readiness, payload execution, keyboard layout changes, Armory upload activity, and validation/storage faults.
- Fault LED patterns repeat until a newer status event is queued, matching the intent of the MicroPython halt patterns without blocking firmware recovery paths.
- Firmware status pattern map matching the existing MicroPython status LED timings for supported stage and error names.

### Changed

- Cargo package version bumped to `0.1.1`.
- Types that derive `Debug` now also derive or implement `defmt::Format` for firmware logging.
- Removed dead-code suppressions from parser, keyboard, storage, and status LED paths by deleting unused wrappers or wiring the underlying behavior.
- README, PR, and release notes updated for the status LED release.

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
- Signed release packaging for ELF and UF2 artifacts.

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
