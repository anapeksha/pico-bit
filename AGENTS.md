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

---

## 3. Strict Architectural Rules & Constraints

### Memory Management (Zero-Heap Policy)
* **No Dynamic Allocation:** The use of `alloc`, `Box`, `Vec`, or the standard `String` type is strictly forbidden. 
* **Buffer Strategy:** Always use fixed-size stack buffers (e.g., `[u8; 1024]`) for tasks like reading incoming HTTP bodies or streaming to flash.
* **Global State:** Shared state (like `SharedStorage` or `StagingBuffer`) must be initialized via static mutables or global atomic pointers, protected by `embassy` critical section mutexes.
* **Custom Deserialization:** When handling large incoming strings (like a multi-KB DuckyScript payload), use custom `serde::de::Visitor` implementations to stream unescaped characters directly into a statically allocated scratch buffer, rather than allocating a temporary string.
* **Serialization of Dynamic Lists:** Do not allocate response lists. Use fixed arrays plus manual chunked JSON writers when exposing LittleFS file listings or other bounded dynamic data.

### Picoserve Routing Rules
* **Static vs. Dynamic Endpoints:** Do not mix raw string matching with dynamic variable extraction in the same `.route()` call block.
* **Path Segments:** To extract URL parameters (like `/:filename`), you **must** use `picoserve::routing::parse_path_segment`.
* **String Allocation in Routes:** `parse_path_segment` uses `FromStr`. Because we cannot use `std::string::String`, you must extract path variables into a `heapless::String` (e.g., `parse_path_segment::<heapless::String<64>>()`). Handlers will receive this as an argument and can access the inner string using `.as_str()`.

### Picoserve Response & Handler Patterns
* **Standard Returns:** Route handlers should generally return `impl IntoResponse`. For API responses, return a tuple of `(StatusCode, Json<T>)` or just `Json<T>`.
* **Avoiding Trait Bounds Errors:** Do not inject `picoserve::response::ResponseWriter` into standard handler arguments to try and manually write headers. The framework relies on specific trait boundaries (`RequestHandlerFunction`). Construct responses natively using `Json` and status codes instead.
* **Service-Level Streaming:** If an endpoint needs both a path parameter and direct request-body streaming, use `RequestHandlerService` with `post_service`. Keep the controller as a route adapter; put the streaming service object and upload loop in the API service module.
* **Streaming Transfers:** When uploading/downloading raw files, do not read the entire file into memory. Uploads and downloads stream between picoserve and LittleFS in small loop chunks, currently 1 KB for Armory. `/api/bootstrap` stays fixed-length JSON. Variable startup data such as Armory, payload text, and runs may use chunked transfer to avoid response buffering.
* **Lean GET Contracts:** Firmware GET endpoints should return machine state only: booleans, short codes, filenames, sizes, and URLs when necessary. Do not send UI labels, friendly names, hints, or success messages from read-only endpoints; keep those in the frontend.
* **HTTP Ownership:** Keep route contracts in picoserve controllers and service modules. The HTTP workers may also serve bounded startup and asset responses directly when hardware testing shows that path is required for browser stability; do not add a second routing system or ad hoc endpoint names.

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
  Manages the single replaceable binary under `/armory` in LittleFS and exposes the bounded file table through `GET /api/armory`. File list entries contain only `kind`, `name`, and `size`; the frontend derives URLs/labels. Upload route is `POST /api/armory/upload/:filename`; each successful upload removes the previous Armory binary before writing the new file. Delete route is `DELETE /api/armory/:filename`. Downloads are available through `GET /api/armory/:filename`; Wi-Fi may serve `payload.dd`, but NCM must serve only the staged Armory binary. Uploads and downloads stream in 1 KB chunks and must reject files above `750 * 1024` bytes. The frontend must validate this too using its local 750 KB limit.
* **Payload Engine (`src/net/http/api/payload/`):**
  Accepts DuckyScript text via JSON. Uses a zero-allocation staging buffer to parse syntax line-by-line (`DuckyParser`) before overwriting `payload.dd`. `GET /api/payload` streams the current editor text as chunked JSON, bounded by the 2 KB payload buffer. The saved payload file is always `payload.dd`; do not use or reintroduce `payload.txt`.
* **Runs (`src/net/http/api/runs/`):**
  Exposes recent run metadata and seeded state through `GET /api/runs`. Run history entries contain only compact metadata such as `ok`, `sequence`, `source`, and `preview`.
* **Storage (`src/storage/manager.rs`):**
  Owns LittleFS read/write/truncate/append/list helpers. It must create `/armory` and ensure `payload.dd` exists after mount. `list_files` returns bounded `ListedFile` entries from `/` and `/armory`.
* **Runtime Runners (`src/runners/`):**
  `mod.rs` exports only the Embassy task functions required by `main.rs`. `usb.rs` owns USB, NCM, USB DHCP, and Host HID execution. `wifi.rs` owns CYW43 AP bring-up. `http.rs` owns the accepted-socket HTTP worker loop, small preflight, bounded startup responses, NCM Armory streaming, and picoserve prefix replay fallback. The same worker task runs once on Wi-Fi (`192.168.4.1`) and once on USB NCM (`192.168.7.1`). The NCM surface must expose only `/api/armory` and `/api/armory/:filename`, and `/api/armory/:filename` must reject `payload.dd` on NCM so only the staged binary is delivered there; all other dashboard/API routes remain portal-only on Wi-Fi. On hardware, routing Safari dashboard hydration entirely through the generic picoserve serve path reproduced firmware faults; keep `/`, `/api/bootstrap`, `/api/armory`, `/api/armory/:filename`, `/api/payload`, `/api/payload/run`, `/api/runs`, browser probes, OPTIONS, and `/api/keyboard/layout` on the bounded startup path unless hardware testing proves a replacement. HID execution reads and executes `payload.dd`; if missing in the expected way, use the existing fallback behavior. Do not point runtime execution back to `payload.txt`.
* **Static Dashboard (`src/net/http/assets.rs`):**
  Serves only the gzipped single-file dashboard artifact from `dist/index.html.gz` through picoserve with `Content-Encoding: gzip`. Do not serve separate JS/CSS assets from firmware.
---

## 5. Device State Contracts

* **Only Two USB/Transport States:** Track **Host HID** and **NCM Link**. Do not reintroduce `usb_agent`, `UsbState`, mass-storage mount state, or generic "USB agent" naming in API contracts or frontend stores.
* **Host HID:** Represents the keyboard/HID typing channel.
* **NCM Link:** Represents the USB NCM network transport and web root (`http://192.168.7.1` by default). Binary Armory delivery state belongs here, not under Host HID.
* **Protected Payload File:** `payload.dd` is editor-managed and must not be deletable from the Armory delete API or UI.
* **No Portal Auth State:** Device/bootstrap contracts should not expose portal login state. AP SSID/password are Wi-Fi access-point details, not portal authentication.
* **No Bootstrap Validation:** Validation is action-scoped state, not device snapshot state. Keep validation out of `/api/bootstrap`, bootstrap stores, and the development mock response.
* **No Variable Bootstrap Data:** LittleFS file entries, current payload text, and recent run history are not bootstrap fields. They belong to `/api/armory`, `/api/payload`, and `/api/runs`.
* **Frontend-Owned Labels:** Keyboard layout/OS option labels, NCM/Host HID display strings, upload-limit copy, and success text for read-only snapshots are frontend-owned.

---

## 6. Frontend Data Flow

* **Contracts:** API response/request shapes live in `web/src/api/contracts.ts`. Keep frontend types aligned with firmware JSON fields.
* **Client:** HTTP calls live in `web/src/api/client.ts`.
* **Bootstrap Cache:** `web/src/stores/bootstrapCache.ts` is the app-level cache layer. Startup hydration fetches `/api/bootstrap`, `/api/armory`, `/api/payload`, and `/api/runs` in sequence and applies one composed state. Mutations refresh through the same composed hydration path.
* **Optimistic Mutations:** Frontend mutations should update state optimistically, then refresh bootstrap. Revert to the captured snapshot only if the bootstrap refresh fails.
* **Keyboard Target:** Keyboard target selection consists only of operating system plus keyboard layout. Layout controls printable `STRING` character-to-HID mapping; OS controls key-chord aliases such as `COMMAND`, `OPTION`, and `WINDOWS`. Do not show or store a separate "Profile" field; it is just a derived combination of OS/layout. Do not persist keyboard target in browser storage. Bootstrap applies the firmware-reported target, and the frontend calls `/api/keyboard/layout` only when the user changes the controls.
* **Editor Validation:** DuckyScript validation should run only on explicit save/save-run flows, not on every keystroke and not during bootstrap. The Save button posts the payload for firmware validation; if valid, the frontend immediately calls the run endpoint. If invalid, open `ValidationModal` with the returned validation response.
* **Binary Armory UI:** Render files from `/api/armory`. Show `payload.dd`, but disable delete for it. Treat Armory as one replaceable binary: optimistic upload state should replace the previous asset row and keep only `payload.dd` plus the selected binary. Upload validation must enforce the frontend-owned 750 KB limit.
* **Network Stager Reference:** Windows uses PowerShell examples; macOS and Linux use `curl`.
* **No Login UI:** Do not add login forms, auth body classes, auth props, `/login` form posts, or `/logout` handlers in the Svelte app.

## 7. Runtime/Worker Constraints

* **HTTP Worker Count:** The dashboard is a single static request, so Wi-Fi still uses one accepted-socket HTTP worker. USB NCM uses a second accepted-socket HTTP worker only for `http://192.168.7.1/api/armory` and the staged binary at `http://192.168.7.1/api/armory/:filename`. Do not raise the worker pool just to support separate JS/CSS assets; fix the frontend bundle instead.
* **Straightforward Startup:** Dashboard startup should be explicit and boring: load `/`, then hydrate through the frontend client. Do not add hidden browser-storage restore flows that call mutation APIs during startup. The HTTP worker owns the bounded startup responses listed above because this is the hardware-stable path.
* **Build Ordering:** `cargo check`/`cargo build` include `dist/index.html.gz`. Run `npm --prefix web run build` first when the artifact may be missing or stale.
* **CI Cargo Builds:** GitHub Actions use normal Cargo commands for firmware validation and release builds.
* **Small Bootstrap Required:** `/api/bootstrap` must stay a small fixed contract and direct fixed-length JSON response. Do not add LittleFS reads, payload text, file tables, run history, validation, or other variable-sized fields back into bootstrap.
* **Chunk Only Variable Startup Data:** The gzipped dashboard asset, Armory listing/downloads, payload text, and runs may be chunked. Bootstrap should not be chunked. Do not use chunked transfer for small mutation responses.
* **Static Asset Writes:** Keep dashboard write slices below the TCP tx buffer size. If the HTTP worker tx buffer in `src/runners/http.rs` changes, verify the static dashboard chunk size remains safely smaller.

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
