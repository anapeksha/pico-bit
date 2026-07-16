# Changelog

All notable changes to Pico Bit are documented in this file.

## Unreleased

## v0.2.2 - 2026-07-16

### Added

- WPA2/WPA3 transition-mode security for the Pico Bit Wi-Fi access point, allowing WPA3-capable clients to use SAE while retaining WPA2 compatibility.
- A narrow local `cyw43` 0.7.0 patch containing the upstream SoftAP WPA3 work merged in `embassy-rs/embassy#6529`.

### Changed

- Access-point management-frame protection is now capable in transition mode, and AP encryption remains AES-only.
- Vendored CYW43 source records its upstream merge provenance and retains the upstream MIT OR Apache-2.0 license files.

## v0.2.1 - 2026-07-15

### Changed

- Split the Wi-Fi portal and USB NCM HTTP workers so the restricted NCM delivery task no longer carries the portal router future or portal-sized buffers.
- Reworked the picoserve Armory list response as bounded chunked JSON with non-blocking LittleFS snapshot refreshes.
- Replaced the custom picoserve prefix-replay socket with explicit preflight inspection and consumption for bounded worker routes.

### Fixed

- Reduced firmware static RAM use by about 54 KB by sizing the NCM worker for its restricted delivery contract.
- Prevented Armory response generation from suspending inside picoserve while waiting for LittleFS or listing scratch locks.
- Retained the hardware-verified bounded port-80 Armory path after confirming that preflight-to-picoserve socket handoff remains unstable on RP2350.

## v0.2.0 - 2026-07-15

### Added

- Persistent keyboard OS and layout configuration in the internal `/keyboard.cfg` LittleFS file.
- Portal-only `GET /api/metrics` endpoint for LittleFS capacity, staged binary size, last run result, and latest upload transfer metrics.
- Explicit NCM delivery policy limiting the USB network surface to staged binary metadata and `/api/armory/payload.bin` download.
- Bounded frontend activity timeline for payload, Armory, and keyboard target actions.
- Staged binary delivery details, including exact size, NCM availability, and direct NCM URL.
- Clickable validation diagnostics that focus the matching editor line and column.

### Changed

- Switched the default local firmware runner from `probe-rs run` to `cargo embed --path`, with `cargo-embed` now owning the standard flash and RTT workflow.
- Keyboard target changes now persist in firmware storage instead of relying on browser state.
- Armory upload, delete, and payload save/run responses now expose short machine-readable result codes.
- Dashboard transport state now distinguishes Wi-Fi control, Host HID execution, and NCM binary delivery.
- Editor actions remain visible in a sticky toolbar and show the active OS/layout target beside the script.

### Fixed

- Kept hardware-sensitive dashboard hydration and Armory transfers on the bounded HTTP worker path after generic picoserve routing reproduced RP2350 firmware faults under Safari.

## v0.1.3 - 2026-07-09

### Changed

- Package bump.
- Armory upload now uses `POST /api/armory/upload` and always replaces `/armory/payload.bin`.
- Armory upload holds the LittleFS storage lock across the request stream, opens `/armory/payload.bin` once, writes bounded chunks, and closes the file exactly once to avoid RAM pressure and LittleFS metadata churn.
- Armory upload now uses a 4 KB TCP receive/write buffer to reduce LittleFS append cycles during browser uploads.
- Portal and NCM Armory downloads now target the fixed staged binary name `payload.bin`.
- Armory delete now uses the bounded HTTP worker path and returns the same mutation JSON contract as upload.
- Wi-Fi upload handling now stays on the bounded HTTP worker path instead of falling through to the generic picoserve fallback.

### Fixed

- Fixed frontend upload calls still targeting the old `/api/armory/upload/:filename` route.
- Fixed firmware crash when `/api/armory/upload` reached the generic picoserve serve path.
- Fixed Armory delete failures caused by `DELETE /api/armory/:filename` reaching the generic picoserve serve path.

## v0.1.2 - 2026-07-08

### Added

- Icons addition for armory buttons.

### Changed

- Package bump.
- Added repository license.

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
