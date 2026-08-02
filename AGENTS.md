# AGENTS.md: pico-bit Project Context

This file provides strict architectural context, constraints, and learned patterns for the `pico-bit` embedded Rust project. AI agents should reference this document before touching firmware, API, storage, or frontend integration code.

---

## 1. Project Overview
* **Project Name:** `pico-bit`
* **Target Hardware:** Raspberry Pi Pico 2 / RP2350 (Target: `thumbv8m.main-none-eabihf`).
* **Core Purpose:** An embedded HTTP server, Host HID injector, and USB NCM file delivery surface. It serves files from LittleFS through the Armory/NCM web root and parses/executes the single saved DuckyScript payload on demand.
* **Environment:** Strict **`no_std`** bare-metal environment.

## 2. Core Tech Stack
* **Web Server:** `picoserve` (Async HTTP server for `no_std` environments).
* **Storage:** `littlefs2` wrapper over localized flash memory.
* **Concurrency:** `embassy_sync` (`Mutex<CriticalSectionRawMutex, RefCell<T>>`, `AtomicBool`).
* **Serialization:** `serde` with `heapless` integrations.
* **Frontend:** Svelte, bundled as a single gzipped dashboard artifact embedded into flash.
* **Default Local Flash/Debug Tool:** `cargo-embed`, configured by the committed `Embed.toml`.
* **Field Logging:** A dedicated Embassy `debug_task` owns TX-only SPI0 and drains bounded ASCII records produced by `debug_log!`. SPI field logging complements RTT and allows capture without a debug probe.
* **Wi-Fi AP Security:** WPA2/WPA3 transition mode with AES. The local `cyw43` patch is sourced from upstream merge commit `5763f62d945576afcb0442bfec433e853809cf5f` and should be removed after upgrading to a crates.io release containing that change.

---

## 3. Strict Architectural Rules & Constraints

### Memory Management (Zero-Heap Policy)
* **No Dynamic Allocation:** The use of `alloc`, `Box`, `Vec`, or the standard `String` type is strictly forbidden. 
* **Buffer Strategy:** Always use fixed-size stack buffers (e.g., `[u8; 1024]`) for tasks like reading incoming HTTP bodies or streaming to flash.
* **Global State:** Shared state (like `SharedStorage` or `StagingBuffer`) must be initialized via static mutables or global atomic pointers, protected by `embassy` critical section mutexes.
* **Custom Deserialization:** When handling large incoming strings (like a multi-KB DuckyScript payload), use custom `serde::de::Visitor` implementations to stream unescaped characters directly into a statically allocated scratch buffer, rather than allocating a temporary string.
* **Serialization of Dynamic Lists:** Do not allocate response lists. Use fixed arrays plus manual chunked JSON writers when exposing LittleFS file listings or other bounded dynamic data.

### SPI Field Logging Rules
* **Dedicated Ownership:** Only `src/runners/debug.rs::debug_task` and `src/debug/manager.rs::DebugManager` may own or write SPI0. Producers must use `debug_log!`; do not write to the SPI peripheral from HTTP, HID, storage, Wi-Fi, or status code.
* **Fixed Transport:** SPI field output uses SPI0 at 31.25 MHz with GP2 as SCK, GP3 as MOSI, DMA channel 2, no MISO, and no chip-select. Records are ASCII terminated by `\r\n`; this is not a UART stream.
* **Bounded Messages:** The log channel contains 16 fixed `heapless::String<96>` records. Messages longer than the record capacity are truncated while preserving the CRLF terminator. Do not add heap allocation for logging.
* **Never Block Firmware Work:** `debug_log!` formats synchronously and enqueues with `try_send`. If the channel is full, the record must be dropped. Do not replace this with `send(...).await` or otherwise allow diagnostics to delay USB, HID, networking, HTTP, status, or LittleFS work.
* **Low-Volume Events Only:** Log state transitions, completed mutations, bounded sizes/durations, short result codes, and actionable failures. Do not log packets, HID characters, upload chunks, dashboard hydration GETs, or other high-frequency paths.
* **Sensitive Data:** Never write the AP password, payload/DuckyScript contents, run previews, uploaded binary contents, keyboard reports, secrets, or request bodies to SPI logs. SSID, fixed route/path names, compact OS/layout codes, byte counts, line numbers, and machine result codes are acceptable.
* **Failure Semantics:** An absent receiver cannot block TX-only SPI. A stalled or failed SPI writer may stop only the debug task; application tasks must remain independent. SPI write failures can be reported through RTT because the SPI output itself is unavailable.
* **Physical Reliability:** 31.25 MHz requires short wiring, a shared ground, and a capable receiver. If field hardware cannot capture it reliably, lower the SPI clock deliberately and update this file plus `README.md`; do not mistake capture corruption for a firmware execution failure.

### Picoserve Routing Rules
* **Static vs. Dynamic Endpoints:** Do not mix raw string matching with dynamic variable extraction in the same `.route()` call block.
* **Path Segments:** To extract URL parameters (like `/:filename`), you **must** use `picoserve::routing::parse_path_segment`.
* **String Allocation in Routes:** `parse_path_segment` uses `FromStr`. Because we cannot use `std::string::String`, you must extract path variables into a `heapless::String` (e.g., `parse_path_segment::<heapless::String<64>>()`). Handlers will receive this as an argument and can access the inner string using `.as_str()`.

### Picoserve Response & Handler Patterns
* **Standard Returns:** Route handlers should generally return `impl IntoResponse`. For API responses, return a tuple of `(StatusCode, Json<T>)` or just `Json<T>`.
* **Avoiding Trait Bounds Errors:** Do not inject `picoserve::response::ResponseWriter` into standard handler arguments to try and manually write headers. The framework relies on specific trait boundaries (`RequestHandlerFunction`). Construct responses natively using `Json` and status codes instead.
* **Service-Level Streaming:** If an endpoint needs both a path parameter and direct request-body streaming, use `RequestHandlerService` with `post_service`. Keep the controller as a route adapter; put the streaming service object and upload loop in the API service module.
* **Streaming Transfers:** When uploading/downloading raw files, do not read the entire file into memory. Armory upload uses a 4 KB bounded worker buffer; Armory downloads stream in 1 KB chunks. `/api/bootstrap` stays fixed-length JSON. Variable startup data such as Armory, payload text, and runs may use chunked transfer to avoid response buffering.
* **Lean GET Contracts:** Firmware GET endpoints should return machine state only: booleans, short codes, filenames, sizes, and URLs when necessary. Do not send UI labels, friendly names, hints, or success messages from read-only endpoints; keep those in the frontend.
* **HTTP Ownership:** Keep route contracts in picoserve controllers and service modules. The HTTP workers may also serve bounded startup and asset responses directly when hardware testing shows that path is required for browser stability; do not add a second routing system or ad hoc endpoint names. Raw picoserve on an untouched accepted socket is functional, but passing a socket to picoserve after portal preflight inspection faults the RP2350. A future migration must give picoserve sole ownership of the portal socket from `accept`; do not migrate individual port-80 routes through the current preflight handoff.

### API Layout Rules
* **Folder Per API Surface:** Each API surface lives in its own folder under `src/net/http/api/<name>/`.
* **Separation of Concerns:** Each API folder must contain:
  * `mod.rs`: exposes only the relevant controller module.
  * `controller.rs`: picoserve routing and input handoff only. Keep it thin, like bootstrap.
  * `service.rs`: bounded data models, response construction, storage access, validation, streaming services, and business behavior.
* **Router Wiring:** Tie API controllers only through `src/net/http/mod.rs`. Do not reintroduce flat `armory.rs`, `payload.rs`, or `status.rs` API files.
* **No Status API:** The old status endpoint was only a liveness stub and must not be used as a frontend data source.
* **No Portal Auth API:** The frontend no longer has login/logout or portal auth state. Do not reintroduce `/login`, `/logout`, `auth_enabled`, `authState`, or auth-specific frontend props unless the product requirement explicitly changes.

### Frontend Build Rules
* **Single Request Dashboard:** The firmware serves only `/` for the dashboard. JavaScript and CSS must be inlined into HTML at build time so the Pico does not need multiple static asset workers.
* **External Build Plugins:** Use `vite-plugin-singlefile` for JS/CSS inlining and `vite-plugin-compression` for gzip output. Do not reintroduce a custom Vite plugin for responsibilities covered by these packages.
* **Embedded Artifact:** The firmware includes `dist/index.html.gz` and serves it as `text/html` with `Content-Encoding: gzip`. Do not include `dist/index.html`, `assets/index.js`, or `assets/index.css` from firmware.
* **Vite Proxy:** The development proxy should proxy `/api` only. Do not add `/login` or `/logout`.

---

## 4. Key Subsystems

* **Bootstrap (`src/net/http/api/bootstrap/`):**
  The fixed startup device snapshot. It returns AP settings, `host_hid_active`, `ncm_active`, `ncm_url`, keyboard OS/layout codes, and `seeded`. It must not read LittleFS and must not return files, payload text, run history, validation state, upload limits, labels, hints, or messages. Because the contract is small and fixed, it should return normal `Json<T>`, not `ChunkedResponse`.
* **Armory (`src/net/http/api/armory/`):**
  Manages the single replaceable binary at `/armory/payload.bin` in LittleFS and exposes the bounded file table through `GET /api/armory`. File list entries contain only `kind`, `name`, and `size`; the frontend derives URLs/labels. The picoserve list response writes bounded chunked JSON and refreshes its fixed snapshot only through non-blocking storage/scratch locks. On port 80, listing, upload, delete, and download remain on the hardware-verified bounded worker path until picoserve can own the portal socket from `accept`. Each successful upload removes previous Armory files, opens `/armory/payload.bin` once with create/truncate flags, writes request chunks while holding the storage lock, and closes the file exactly once. Delete route is `DELETE /api/armory/:filename` and must reject `payload.dd`. Downloads are available through `GET /api/armory/:filename`; Wi-Fi may serve `payload.dd`, but NCM must serve only `/api/armory/payload.bin`. Uploads use a 4 KB TCP/read/write buffer on the bounded worker path; downloads stream in 1 KB chunks. All uploads must reject files above `750 * 1024` bytes. The frontend must validate this too using its local 750 KB limit.
* **Payload Engine (`src/net/http/api/payload/`):**
  Accepts DuckyScript text via JSON. Uses a zero-allocation staging buffer to parse syntax line-by-line (`DuckyParser`) before overwriting `payload.dd`. `GET /api/payload` streams the current editor text as chunked JSON, bounded by the 2 KB payload buffer. The saved payload file is always `payload.dd`; do not use or reintroduce `payload.txt`. Save validation is parser-level validation, not proof that every parsed extended command is implemented by `DuckyExecutor`. The dependable runtime includes comments, delay/default delay, printable strings, key sequences, basic variables, and conditional blocks. `WHILE` does not currently jump back, and parsed functions, `REPEAT`, `HOLD`, and `RELEASE` are not complete runtime features; do not advertise them as fully executable without implementing control flow and regression tests.
* **Runs (`src/net/http/api/runs/`):**
  Exposes recent run metadata and seeded state through `GET /api/runs`. Run history entries contain only compact metadata such as `ok`, `sequence`, `source`, and `preview`.
* **Metrics (`src/net/http/api/metrics/`):**
  Exposes a compact portal-only snapshot through `GET /api/metrics`: estimated free LittleFS bytes, staged binary bytes, the latest payload run code, and the latest upload byte/duration counters. Keep this contract fixed, machine-oriented, and off the NCM surface.
* **Storage (`src/storage/manager.rs`):**
  Owns LittleFS read/write/truncate/append/list helpers. It must create `/armory` and ensure `payload.dd` exists after mount. `list_files` returns bounded `ListedFile` entries from `/` and `/armory`. `/keyboard.cfg` is internal device configuration and must not appear in Armory listings or deletion paths.
* **NCM Delivery (`src/net/http/delivery.rs`):**
  Defines the staged binary name/path and the restricted NCM route policy. NCM serves only Armory metadata and `/api/armory/payload.bin`; portal API behavior remains separate.
* **Runtime Runners (`src/runners/`):**
  `mod.rs` exports only the Embassy task functions required by `main.rs`. `usb.rs` owns USB, NCM, USB DHCP, and Host HID execution. `wifi.rs` owns CYW43 AP bring-up. `http.rs` owns separate Wi-Fi portal and restricted NCM accepted-socket tasks, small preflight, bounded startup responses, and NCM Armory streaming. `debug.rs` exclusively owns the SPI debug writer and drains `LOG_CHANNEL`. The NCM task uses smaller fixed buffers and exposes only `/api/armory` and `/api/armory/:filename`; `/api/armory/:filename` rejects `payload.dd` so only the staged binary is delivered there. All other dashboard/API routes remain portal-only on Wi-Fi. Hardware testing established that raw picoserve works when it receives an untouched accepted socket, while handing it a socket after preflight inspection faults the RP2350 before controller execution. Keep `/`, `/api/bootstrap`, `/api/armory`, `/api/armory/:filename`, `/api/payload`, `/api/payload/run`, `/api/runs`, `/api/metrics`, browser probes, OPTIONS, and `/api/keyboard/layout` on the bounded startup path. A later migration must replace the portal worker as one unit so picoserve owns the socket from `accept`; do not move these routes one at a time through preflight. HID execution reads and executes `payload.dd`; if missing in the expected way, use the existing fallback behavior. `POST /api/payload/run` validates the saved file and arms an atomic trigger; it does not wait for completed HID execution. The HID task polls that trigger every 100 ms and records the eventual result. Do not point runtime execution back to `payload.txt`.
* **Status LED (`src/status.rs`):**
  Controls the physical on-board monochrome green user LED via the CYW43 wireless chip handle. Status events are queued asynchronously through a bounded `embassy_sync::Channel` and processed sequentially by a dedicated status Embassy task. Instead of driving hardware directly, this task converts state milestones into high/low binary states and publishes them via an `embassy_sync::signal::Signal`. The `wifi_led_driver_task` in the wireless runner intercepts this signal and passes it to `control.gpio_set(0, state)`. `main.rs` must preserve the established initialization order: spawn `status::task()`, queue `Stage::Boot`, then spawn `debug_task`. SPI logging is complementary and must not replace, delay, or reorder status initialization.
* **SPI Field Logger (`src/debug/`, `src/runners/debug.rs`):**
  `DebugLogger` formats each event into a fixed 96-byte record, preserves CRLF framing, and uses non-blocking `LOG_CHANNEL.try_send`. `debug_task` is the sole consumer and passes records to `DebugManager`, which writes through TX-only SPI0 using DMA channel 2. Current categories include `BOOT`, `STORAGE`, `WIFI`, `USB`, `NCM`, `HTTP`, `HID`, `KEYBOARD`, `ARMORY`, and `PAYLOAD`. The logger is best-effort observability: dropped records are acceptable; delayed application work is not. The current queue payload capacity is 1,536 bytes, excluding channel metadata.
* **Static Dashboard (`src/net/http/assets.rs`):**
  Serves only the gzipped single-file dashboard artifact from `dist/index.html.gz` through picoserve with `Content-Encoding: gzip`. Do not serve separate JS/CSS assets from firmware.
---

## 5. Device State Contracts

* **Only Two USB/Transport States:** Track **Host HID** and **NCM Link**. Do not reintroduce `usb_agent`, `UsbState`, mass-storage mount state, or generic "USB agent" naming in API contracts or frontend stores.
* **Host HID:** Represents the keyboard/HID typing channel.
* **NCM Link:** Represents the USB NCM network transport and web root (`http://192.168.7.1` by default). Binary Armory delivery state belongs here, not under Host HID.
* **Protected Payload File:** `payload.dd` is editor-managed and must not be deletable from the Armory delete API or UI.
* **Internal Keyboard Configuration:** `/keyboard.cfg` stores firmware-owned OS/layout codes, survives reboot, and is never an Armory asset.
* **No Portal Auth State:** Device/bootstrap contracts should not expose portal login state. AP SSID/password are Wi-Fi access-point details, not portal authentication.
* **No Bootstrap Validation:** Validation is action-scoped state, not device snapshot state. Keep validation out of `/api/bootstrap`, bootstrap stores, and the development mock response.
* **No Variable Bootstrap Data:** LittleFS file entries, current payload text, and recent run history are not bootstrap fields. They belong to `/api/armory`, `/api/payload`, and `/api/runs`.
* **Frontend-Owned Labels:** Keyboard layout/OS option labels, NCM/Host HID display strings, upload-limit copy, and success text for read-only snapshots are frontend-owned.

---

## 6. Frontend Data Flow

* **Contracts:** API response/request shapes live in `web/src/api/contracts.ts`. Keep frontend types aligned with firmware JSON fields.
* **Client:** HTTP calls live in `web/src/api/client.ts`.
* **Bootstrap Cache:** `web/src/stores/bootstrapCache.ts` is the app-level cache layer. Startup hydration fetches `/api/bootstrap`, `/api/armory`, `/api/payload`, `/api/runs`, and `/api/metrics` in sequence and applies one composed state. Mutations refresh through the same composed hydration path.
* **Optimistic Mutations:** Frontend mutations should update state optimistically, then refresh bootstrap. Revert to the captured snapshot only if the bootstrap refresh fails.
* **Keyboard Target:** Keyboard target selection consists only of operating system plus keyboard layout. Layout controls printable `STRING` character-to-HID mapping; OS controls key-chord aliases such as `COMMAND`, `OPTION`, and `WINDOWS`. Do not show or store a separate "Profile" field; it is just a derived combination of OS/layout. Do not persist keyboard target in browser storage. Firmware persists valid changes to `/keyboard.cfg`, bootstrap reports the restored target, and the frontend calls `/api/keyboard/layout` only when the user changes the controls.
* **Editor Validation:** DuckyScript validation should run only on explicit save/save-run flows, not on every keystroke and not during bootstrap. The Save button posts the payload for firmware validation; if valid, the frontend immediately calls the run endpoint. If invalid, open `ValidationModal` with the returned validation response. Diagnostic selection must focus the corresponding editor line and column.
* **Binary Armory UI:** Render files from `/api/armory`. Show `payload.dd`, but disable delete for it. Treat Armory as one replaceable binary: optimistic upload state should replace the previous asset row and keep only `payload.dd` plus the selected binary. Upload validation must enforce the frontend-owned 750 KB limit.
* **Network Stager Reference:** Windows uses PowerShell examples; macOS and Linux use `curl`.
* **Activity Timeline:** Keep action history session-local and bounded to six resolved actions. It is operational feedback, not a persistent or verbose logging system.
* **No Login UI:** Do not add login forms, auth body classes, auth props, `/login` form posts, or `/logout` handlers in the Svelte app.

## 7. Runtime/Worker Constraints

* **HTTP Worker Count:** The dashboard is a single static request, so Wi-Fi still uses one accepted-socket HTTP worker. USB NCM uses a second accepted-socket HTTP worker only for `http://192.168.7.1/api/armory` and the staged binary at `http://192.168.7.1/api/armory/:filename`. Do not raise the worker pool just to support separate JS/CSS assets; fix the frontend bundle instead.
* **Straightforward Startup:** Dashboard startup should be explicit and boring: load `/`, then hydrate through the frontend client. Do not add hidden browser-storage restore flows that call mutation APIs during startup. The HTTP worker owns the bounded startup responses listed above because this is the hardware-stable path.
* **Build Ordering:** `cargo check`/`cargo build` include `dist/index.html.gz`. Run `npm --prefix web run build` first when the artifact may be missing or stale.
* **CI Cargo Builds:** GitHub Actions use normal Cargo commands for firmware validation and release builds.
* **Local Runner Ownership:** `.cargo/config.toml` routes `cargo run` directly through `cargo embed --path` using the committed `Embed.toml`. Let `cargo-embed` own probe attach, flashing, RTT, and GDB profiles.
* **Small Bootstrap Required:** `/api/bootstrap` must stay a small fixed contract and direct fixed-length JSON response. Do not add LittleFS reads, payload text, file tables, run history, validation, or other variable-sized fields back into bootstrap.
* **Chunk Only Variable Startup Data:** The gzipped dashboard asset, Armory listing/downloads, payload text, and runs may be chunked. Bootstrap and metrics should use fixed-length bounded JSON. Do not use chunked transfer for small mutation responses.
* **Static Asset Writes:** Keep dashboard write slices below the TCP tx buffer size. If the HTTP worker tx buffer in `src/runners/http.rs` changes, verify the static dashboard chunk size remains safely smaller.
* **Logging Resource Ownership:** SPI0, GP2, GP3, and DMA channel 2 are permanently reserved for field logging in the firmware build. Do not assign them to another peripheral without removing or redesigning `debug_task` and updating the capture documentation.
* **Logging Overload Policy:** Do not increase queue depth casually; static RAM is constrained. Prefer fewer, shorter, higher-value events. Queue saturation must drop diagnostics rather than introduce backpressure.
* **Task Independence:** The status LED, SPI logger, Wi-Fi, USB, HID, and HTTP workers are separate Embassy tasks. Logging must not acquire storage, CYW43 control, HTTP socket, or HID locks, and application code must not wait for a log record to be transmitted.

---

## 8. Verification Commands

Use the target-specific firmware check for embedded code:

```sh
cargo check --target thumbv8m.main-none-eabihf
```

Use host-side library tests only for code that is available without firmware features. Because `.cargo/config.toml` defaults Cargo to the embedded target, pass an explicit host target in CI:

```sh
cargo test --lib --no-default-features --target x86_64-unknown-linux-gnu
```

This command includes firmware-agnostic unit tests; run it after changes to DuckyScript parsing, keyboard mapping, or chunked JSON utilities.

Frontend quality gates:

```sh
npm --prefix web run check
npm --prefix web run test
npm --prefix web run lint
npm --prefix web run build
```

SPI field logging hardware smoke test:

1. Connect Pico GP2/SPI0 SCK to the analyzer clock input, GP3/SPI0 MOSI to the analyzer data input, and share GND. Use 3.3 V-compatible inputs.
2. Decode 8-bit, MSB-first SPI using the firmware default mode, starting with Mode 0, at 31.25 MHz. Use at least 125 MS/s capture rate; 250 MS/s or higher is preferred.
3. Start capture before reset, then exercise boot, USB enumeration, dashboard load, keyboard target update, payload save/run, and Armory upload/download/delete.
4. Confirm records remain ASCII and CRLF-delimited, contain no AP password or payload contents, and that normal device behavior continues with no analyzer attached.
5. If decoding is unreliable, inspect wiring and signal integrity first. Any clock-frequency reduction must be reflected in `src/main.rs`, `README.md`, and this file.

A successful compile does not prove physical SPI capture. Do not claim field logging hardware validation unless it was observed on the target board with the configured receiver.
