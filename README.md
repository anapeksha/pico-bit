# Pico Bit

<img src="images/pico-bit.jpeg" alt="Pico Bit home">

`pico-bit` is an open source Rust Embassy project for the Raspberry Pi Pico 2 W. It combines a USB HID DuckyScript runtime and a Wi-Fi-hosted operator portal for authorized security research, lab automation, and defensive validation.

The Pico types payloads over USB, serves a browser UI at `http://192.168.4.1`.

## Highlights

- Boot-time and on-demand execution of `payload.dd`
- Browser editor with save, validate, and run actions
- Line-level dry-run diagnostics in the portal
- Host typing target selection by OS and keyboard layout
- Shared Host USB status for the runtime MSC/HID device
- Single-binary USB staging as `payload.exe` or `payload.bin`
- Live execution timeline plus loot import and `loot.json` download
- Precompiled Svelte 5 + Tailwind v4 frontend embedded in firmware flash
- Frozen UF2 builds plus release metadata with SHA-256 checksums

## Hardware Support

- Supported board: Raspberry Pi Pico 2 W (`RPI_PICO2_W`) only
- Use the Pico's own USB data port for HID and MSC delivery

## Default Access

| What | Value |
|------|-------|
| Wi-Fi SSID | `PicoBit` |
| Wi-Fi password | `PicoBit24Net` |
| Portal URL | `http://192.168.4.1` |
| Portal username | `admin` |
| Portal password | `PicoBit24Admin` |
