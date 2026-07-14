## Summary

Describe the change in 2-5 concrete bullets.

- 
- 

## Why

Explain the user-facing problem, firmware/runtime issue, or maintenance reason this PR addresses.

## Scope

Mark every area touched by this PR.

- [ ] Firmware
- [ ] Frontend
- [ ] Storage / LittleFS
- [ ] HTTP / API contracts
- [ ] USB HID / NCM
- [ ] Wi-Fi / AP
- [ ] Status LED
- [ ] Tooling / CI / Release
- [ ] Docs

## Contract Changes

List any endpoint, JSON shape, route, file-path, or frontend contract changes.

- [ ] No contract changes
- [ ] Updated existing contract(s)
- [ ] Added new contract(s)
- [ ] Removed contract(s)

Details:

```text
GET/POST/DELETE ...
request fields changed:
response fields changed:
frontend contract file updated:
```

## Hardware Impact

Describe what was exercised on real hardware and what was not.

- Board:
- Probe:
- Host OS:
- Verified on device:
- Not verified on device:

## Verification

Mark every command actually run for this PR.

### Frontend

- [ ] `npm --prefix web run format:check`
- [ ] `npm --prefix web run lint -- --max-warnings=0`
- [ ] `npm --prefix web run check`
- [ ] `npm --prefix web test -- --run`
- [ ] `npm --prefix web run build`

### Firmware

- [ ] `cargo fmt --all -- --check`
- [ ] `cargo check --target thumbv8m.main-none-eabihf`
- [ ] `cargo clippy --target thumbv8m.main-none-eabihf --no-deps -- -D warnings -A clippy::new_without_default`
- [ ] `cargo test --lib --no-default-features --target x86_64-unknown-linux-gnu`
- [ ] `cargo run`

Additional notes:

```text
Paste probe/cargo observations here when useful.
```

## Risk Review

Call out the real failure modes.

- Memory / stack / static buffer risk:
- Browser startup / Safari risk:
- Storage corruption / file replacement risk:
- HID execution / keyboard mapping risk:
- NCM / Wi-Fi transport risk:

## Release Notes

State whether the change should be called out in `CHANGELOG.md` / `RELEASE.md`.

- [ ] No release note needed
- [ ] Patch release note
- [ ] Minor release note

Proposed changelog entry:

```text
-
```

## Checklist

- [ ] PR title uses a conventional commit style
- [ ] Imports are clean and moved to the top of touched files
- [ ] No dead code introduced
- [ ] Controllers stay thin; service logic stays in service modules
- [ ] No heap-backed firmware allocation introduced
- [ ] `AGENTS.md` updated if architecture or workflow changed
- [ ] README/docs updated if user workflow changed
