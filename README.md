# Pico Bit

<img src="images/pico-bit.jpeg" alt="Pico Bit home">

`pico-bit` turns a Raspberry Pi Pico 2 W into a Wi-Fi-controlled keystroke injector and lightweight C2 access point. It runs a DuckyScript payload over USB HID, hosts a browser portal at `192.168.4.1`, and can stage one uploaded agent binary for a target machine to fetch and execute.

## Features

- Runs `payload.dd` automatically at boot and on demand from the portal
- Browser editor with reload, save, and save-and-run actions
- Dry-run validation with line-level diagnostics before save or execution
- Host typing target selection by operating system and keyboard layout
- Binary Armory for uploading one staged agent binary at a time
- HID-injected stager generation for Windows, macOS, and Linux targets
- Loot collection and `loot.json` download from the portal
- Recent run history in the portal UI

## Hardware

- Supported board: Raspberry Pi Pico 2 W (`RPI_PICO2_W`) only
- Use the Pico's own USB data port for HID, not a carrier-only power port

## Default access

| What | Value |
|------|-------|
| Wi-Fi SSID | `PicoBit` |
| Wi-Fi password | `PicoBit24Net` |
| Portal URL | `http://192.168.4.1` |
| Portal username | `admin` |
| Portal password | `PicoBit24Admin` |

## Flashing

1. Hold `BOOTSEL` while connecting the Pico to your computer.
2. Download the latest `pico-bit-RPI_PICO2_W-<version>.uf2` from the [Releases page](https://github.com/anapeksha/pico-bit/releases/latest).
3. Copy it to the `RPI-RP2` drive that appears.
4. The board reboots automatically.

On first boot, Pico Bit creates `payload.dd` if it does not already exist.

## Using the portal

1. Plug the Pico into the target machine's USB port.
2. From another device, join the `PicoBit` Wi-Fi network.
3. Open `http://192.168.4.1` and sign in.
4. Edit `payload.dd`, review validation results, then click **Save** or **Save & run**.
5. If needed, change the host typing target under **Layout** so typed characters match the target system.

The payload also runs automatically at boot once the USB keyboard is ready.

## Optional agent workflow

The portal can hold one staged binary in its Armory slot. That binary is served from the Pico, and the portal can inject a one-line stager that downloads and runs it on the target.

1. Open **Binary Armory** in the portal.
2. Upload a binary for the target platform.
3. Choose the target OS.
4. Click **Inject** to type the stager on the target machine.
5. View or download the latest collected data from the **Loot** panel.

Pre-built agent binaries for Windows, Linux, and macOS are attached to each [release](https://github.com/anapeksha/pico-bit/releases/latest).

## Device files

- `payload.dd` is the active HID payload and stays writable on the Pico filesystem
- `keyboard_layout.txt` stores the selected OS + keyboard layout target
- `static/payload.bin` is the currently staged Armory binary
- `loot.json` stores the latest collected loot snapshot

## Development

```bash
uv sync
uv run pytest
uv run python build.py
```

## Responsible use

Use Pico Bit only on systems you own or are explicitly authorized to test. Unauthorized access to computer systems is illegal.

## License

GPL-3.0-only. See `LICENSE`.
