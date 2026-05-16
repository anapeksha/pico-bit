# pico-bit — LLM Reference

**What it is:** A MicroPython DuckyScript runtime + C2 access point for Raspberry Pi Pico 2 W. It types keyboard payloads over USB HID, serves a browser portal over Wi-Fi, and coordinates Rust agent binaries that run on target machines.

**Stack:** MicroPython (Pico) · Svelte 5 + Tailwind v4 (portal) · Rust (agents) · asyncio (server, end-to-end) · uv (Python tooling)

---

## Critical rules — read before touching code

### MicroPython

- **`asyncio.TimeoutError` ≠ builtin `TimeoutError`** — `asyncio.wait_for` raises `asyncio.TimeoutError`. In MicroPython it is NOT a subclass of the builtin. Always catch `asyncio.TimeoutError` directly; add `# noqa: UP041` to silence ruff UP041.
- **Missing `str` methods** — `isalnum()`, `isidentifier()`, `removeprefix()`, `removesuffix()`, `casefold()` all raise `AttributeError` on device. Safe subset: `isalpha()`, `isdigit()`, `isspace()`, `islower()`, `isupper()`, `startswith()`, `endswith()`, `split()`, `strip()`, `replace()`, `encode()`.
- **Exception chaining is dead code** — `raise X from exc` is parsed but the `from` clause is silently ignored. Use `raise X from None`; drop `as exc` to avoid ruff F841/B904.
- **No `typing` module at module level** — function-signature annotations are safe (not evaluated), but `from typing import ...` at module level crashes. It was removed from `ducky/analysis.py`; keep it absent everywhere.
- **~300 KB heap; no concurrent TCP connections** — the Pico W cannot reliably hold two simultaneous TCP connections under load. This drives the non-blocking `inject_binary` design.
- **No async file I/O** — add `await asyncio.sleep(0)` before any `gc.collect()`, `analyze_script()`, file read/write, or crypto call. These yield points prevent event-loop stalls and are load-bearing on hardware.
- **`encrypt`/`decrypt` are async coroutines** — always `await` them. They live in `server/loot_crypto.py`.
- **`_keystream` yields every 8 SHA-256 rounds** — breaks a potential 160 ms CPU block into ~10 ms segments. Do not restructure the crypto loop.

### Server

- **`SetupServer` must stay in `server/__init__.py`** — it is the public singleton. API behavior belongs in `server/api/`; static rendering belongs in `server/app.py`.
- **`inject_binary` must stay non-blocking** — validates, publishes `Detect → success` and `Copy → loading`, returns 200 OK, then schedules HID work via `asyncio.create_task`. Never make it synchronous; that would require two concurrent TCP connections.
- **`_run_payload` catches `Exception` broadly** — `MemoryError`, `RuntimeError`, etc. are real on hardware. The `# noqa: BLE001` is intentional; do not narrow the catch.
- **`POST /api/loot` is unauthenticated** — target machines have no session cookie. This is by design.
- **No `/api/loot/stream` SSE route** — loot is fetched via a one-shot `GET /api/loot` snapshot triggered by the execution stream's `done` event. A persistent loot SSE stream would require two concurrent TCP connections; the Pico cannot sustain this.
- **`loot.json` in the repo root is a static schema reference only** — the Pico writes encrypted binary (PCB1 format) to its own `loot.json` on LittleFS. Tests that call `_init_execution_loot` must monkeypatch `routes_loot._LOOT_FILE` to `tmp_path`.
- **No safe/unsafe mode** — `ALLOW_UNSAFE`, `_safe_mode_enabled()`, `/api/safe-mode`, and the UI toggle are all gone. Do not re-add them.
- **LED calls**: `STATUS_LED.show(key)` plays a non-fatal pattern and returns; `STATUS_LED.halt(key)` loops a fatal pattern forever (requires power cycle). Every LED error call must be wrapped in its own `try/except Exception: pass` so a hardware LED failure does not mask the original error.

### Build

- **`src/web_assets.py` is generated — never edit it** — after any `web/` change: `npm --prefix web run build && uv run python -m scripts.asset_pipeline`. Commit the result; CI fails on drift.
- **`mpy-cross -s` flag** — always pass `<relative-module-path>` (e.g. `server/__init__.py`, `ducky/parser.py`). Without it, temp paths containing `-` produce invalid C identifiers in the frozen firmware.
- **AST bundler order** — block visitors in `scripts/build_pipeline.py` call `generic_visit` before filtering. Reversing this causes empty try/if bodies when conditional imports are the only body statement.
- **Web asset budget** — raw embedded bytes must stay under ~115 KB (currently ~111 KB). Keep new UI dependencies minimal.

### Frontend

- **Tailwind v4 CSS variable shorthand** — use `bg-(--surface)`, not `bg-[var(--surface)]`. The IntelliSense rule `suggestCanonicalClasses` warns on the `[var(...)]` form. All `web/src/` Svelte files now use the short form.
- **Z-index scale is continuous in Tailwind v4** — `z-9999`, `z-1100`, `z-1000` are all canonical. Do not wrap them in `z-[...]`.
- **Svelte Attachments, not Actions** — drag/drop uses `{@attach fileDrop({ onFile: handler })}`. The old `use:fileDrop` syntax is gone; the `actions/` folder was renamed to `attachments/`.
- **`binaryTargetOs` is a derived store** — `derived(keyboard, ($k) => OS_CODE_TO_TARGET[$k.os] ?? 'windows')`. Never replace with a writable store; the OS selection is owned by the keyboard store.
- **Global errors go to `globalError`; render errors go to `showNotice`** — `window.onerror` and `unhandledrejection` write to `globalError` (triggers the full-screen error wall). `<svelte:boundary>` render failures call `showNotice` (toast). Do not swap these.

### DuckyScript stager

- **Keep STRING commands under ~230 chars** — MicroPython fails on long `STRING` commands due to GC fragmentation during double-parse (validate then run). Do not reintroduce `printf '%s\n' ... > "$tmp"` temp-script patterns (~350–620 chars).
- **No `DEFAULTCHARDELAY` on macOS/Linux stagers** — adding even 10 ms inserts 300+ asyncio sleep points during HID typing, causing total failure on real hardware. Windows keeps `DEFAULTCHARDELAY 10` (HID is more tolerant there).
- **`gc.collect()` between validate and run** — `validate_script` allocates a parse tree; `gc.collect()` reclaims it; `run_script` allocates a second. This sequence is intentional; do not remove it.

---

## Repo layout

```
src/
  boot.py              # frozen entry — initializes USB, then imports main
  main.py              # async boot sequence
  keyboard.py          # HID keyboard implementation + layout tables/helpers
  usb.py               # USB singleton + staged-binary filename helpers
  device_config.py     # compile-time defaults (SSID, passwords, CORS)
  web_assets.py        # GENERATED — do not edit
  server/
    __init__.py        # SetupServer class, SERVER singleton, start()
    app.py             # SPA/static renderer; auth-aware shell
    loot_crypto.py     # PCB1 stream cipher — async encrypt/decrypt
    execution_stream.py
    sse.py
    api/
      auth.py          # session/cookie auth mixin
      binary.py        # upload + USB staging mixin
      loot.py          # loot read/write/download + SSE stream mixin
      payload.py       # DuckyScript save/run/validate + keyboard-layout mixin
      usb_agent.py     # USB injector state/control mixin
    _http.py           # constants + stateless utilities only
  ducky/
    lexer.py           # tokenizer
    parser.py          # AST builder
    runtime.py         # DuckyInterpreter, run_script()
    analysis.py        # analyze_script() — dry-run, no typing import
    constants.py       # DEFAULT_PAYLOAD, command lists
web/src/
  App.svelte           # SPA root; login or portal view; global error wall
  stores/              # ap, binary, bootstrap, editor, execution, keyboard,
                       # loot, run, theme, ui, usb
  components/          # portal UI components
  sections/            # TopSection, LeftSection, MiddleSection, RightSection
  attachments/         # Svelte attachments (fileDrop)
  lib/                 # pure helpers: api, binary, loot, editor
  index.css            # Tailwind entrypoint + custom theme tokens
  dev/mock.ts          # local Vite API mocks for UI development
agent/src/bin/
  recon.rs             # full system survey
  exfil.rs             # credential/file grab
  persist.rs           # installs persistence (schtasks/launchd/cron)
  wipe.rs              # clears traces + self-deletes
scripts/
  asset_pipeline.py    # builds web/ and regenerates src/web_assets.py
  build.py             # local artifact builder
  build_pipeline.py    # AST bundler, mpy-cross helpers, config overrides
  release.py           # frozen-firmware release packager
```

---

## API routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/`, `/assets/*` | None | SPA shell + compiled assets |
| any | `/login`, `/logout` | None | Session management |
| POST | `/api/loot` | **None** | Agent phone-home — writes `loot.json` |
| GET | `/api/bootstrap` | Required | Hydrate portal state |
| POST | `/api/payload` | Required | Save `payload.dd` (validates first) |
| POST | `/api/validate` | Required | Dry-run analyze without saving |
| POST | `/api/keyboard-layout` | Required | Set OS + layout, persist to file |
| POST | `/api/run` | Required | Run payload over HID |
| GET | `/api/loot` | Required | Read `loot.json` |
| GET | `/api/loot/download` | Required | Download as `attachment` |
| POST | `/api/loot/import-usb` | Required | Import `loot-usb.json` from USB drive |
| GET/POST | `/api/usb-agent` | Required | USB injector state + activation |
| POST | `/api/inject_binary` | Required | Inject stager over HID (non-blocking) |
| POST | `/api/upload_binary` | Required | Upload binary → `payload.exe`/`payload.bin` |
| GET | `/api/execution/stream` | Required | SSE execution pipeline events |

---

## Encryption at rest

`server/loot_crypto.py` — PCB1 format:

```
derive_key(ssid, password)  →  SHA-256(ssid + ':' + password)  →  32-byte key

encrypt(plaintext, key)  →  b'PCB1' + 4-byte-nonce + XOR(deflate(plaintext))
decrypt(data, key)       →  plaintext
                             (files without PCB1 magic treated as plain UTF-8)
```

Both `payload.dd` and `loot.json` are encrypted at rest. All callers must `await`. Compression uses `deflate.ZLIB` on MicroPython, `zlib` on CPython, raw bytes as fallback.

---

## Execution stream

`/api/execution/stream` is one-way SSE. Pipeline steps: `Detect → Copy → Execute → Collect → Cleanup`. Each step goes `idle → loading → success | error`. A `done` event terminates the stream. The browser calls `GET /api/loot` on `done`.

**Testing the non-blocking handler:**
```python
async def run() -> None:
    await server._handle_api(request, writer)
    await asyncio.sleep(0)  # yield to background task
asyncio.run(run())
```

---

## DuckyScript analysis

`analyze_script(script: str) -> dict` — dry-run, no side effects:

| Key | Type | Notes |
|-----|------|-------|
| `blocking` | bool | True → disable save/run |
| `diagnostics` | list[dict] | each: `code`, `line`, `column`, `severity`, `message`, `hint` |
| `can_run`, `can_save` | bool | derived |
| `summary`, `badge_label`, `badge_tone` | str | UI display |

Diagnostic codes: `parse_error` (blocking), `layout_managed` (warning, from `RD_KBD`).

---

## Build & verify

```bash
# After any web/ change
npm --prefix web run build
uv run python -m scripts.asset_pipeline

# Full local build
uv run python build.py               # → dist/boot.py + dist/mpy/

# Lint + type check
uv run ruff check build.py release.py scripts src tests
uv run ruff format --check .
uv run pyright
npm --prefix web run lint            # 0 errors, ~27 intentional warnings
npm --prefix web run check           # svelte-check

# Tests
uv run pytest                        # 104 backend tests
npm --prefix web run test            # 102 frontend tests

# Verify generated asset sync
uv run python -c "from scripts.asset_pipeline import sync_web_assets; sync_web_assets(check=True)"
```

**Build flags** (generate a configured source tree without modifying tracked files):
`--ap-ssid`, `--ap-password`, `--portal-auth-enabled`, `--portal-username`, `--portal-password`, `--cors-allowed-origin`, `--cors-allow-credentials`

**UI development:**
```bash
npm ci --prefix web
npm --prefix web run dev                                    # local mocks
PICOBIT_PROXY=http://192.168.4.1 npm --prefix web run dev  # proxy to hardware
```

---

## Test coverage (what exists)

**Backend** (`tests/`, 104 tests):
- `test_loot_crypto.py` — PCB1 encrypt/decrypt; wrap calls in `asyncio.run()` (both are async)
- `test_server.py` — SPA rendering, bootstrap, keyboard-layout API, loot save/read/download, USB agent API, inject_binary non-blocking behavior
- `test_routes_binary.py` — upload validation, staging, USB activation
- `test_runtime.py`, `test_parser.py`, `test_lexer.py` — DuckyScript semantics
- `test_build.py` — bundle output, config overrides, `server/__init__.mpy` presence
- `test_asset_pipeline.py` — web asset sync, route aliases, byte budget

**Frontend** (`web/src/**/*.test.ts`, 102 tests):
- `lib/api.test.ts`, `lib/binary.test.ts`, `lib/loot.test.ts`
- `stores/loot.test.ts`, `stores/bootstrap.test.ts`
- `components/LootViewer.test.ts`, `components/ValidationModal.test.ts`, `components/ExecutionTimeline.test.ts`, `components/ThemeToggle.test.ts`
- `attachments/fileDrop.test.ts`

**Not yet tested:** `BinaryArmory` and `DuckyEditor` components.

---

## Open work

- **Hardware validation** — stager inline one-liner fix and full agent injection round-trip not yet confirmed on a real Pico 2 W
- **Component tests** — `BinaryArmory` and `DuckyEditor` have no test files
- **Editor autocomplete** — DuckyScript command autocomplete not implemented
- **macOS frozen builds locally** — only CI (Ubuntu) can complete a UF2 build; ARM newlib toolchain not configured locally
