# Pico Bit

<img src="images/pico-bit.jpeg" alt="Pico Bit home">

`pico-bit` turns a Raspberry Pi Pico 2 W into a wireless keystroke injector and C2 access point. Plug it into a target machine via USB — it types a DuckyScript payload as a keyboard, then starts a Wi-Fi hotspot so you can control everything from a phone or laptop browser.

## What it does

- **Injects keystrokes** — runs `payload.dd` as a USB HID keyboard payload on every boot
- **Browser portal** — edit, save, and run payloads from any device connected to the Pico's Wi-Fi AP
- **Payload library** — store multiple named scripts on-device and load them with one click
- **Keyboard targeting** — choose the target OS and keyboard layout (Windows, macOS, Linux × EN/DE/FR/ES/IT) so typed characters land correctly on any keyboard
- **Agent drop** — upload a small recon or exfil binary to the Pico; the portal injects a one-liner stager that downloads and runs it on the target machine
- **Loot collection** — after an agent runs it phones home and posts collected data back to the Pico; view and download the results from the portal
- **Dry-run validation** — the editor checks your DuckyScript for errors before you save or run it

## Hardware

- Supported board: Raspberry Pi Pico 2 W (`RPI_PICO2_W`) only
- Use the Pico's own USB data port for HID — not a carrier-only power port

## Default access

| What | Value |
|------|-------|
| Wi-Fi SSID | `PicoBit` |
| Wi-Fi password | `PicoBit24Net` |
| Portal URL | `http://192.168.4.1` |
| Portal username | `admin` |
| Portal password | `PicoBit24Admin` |

## Get started

### 1. Flash the firmware

1. Hold `BOOTSEL` while connecting the Pico to your computer.
2. Download the latest `pico-bit-RPI_PICO2_W-<version>.uf2` from the [Releases page](https://github.com/anapeksha/pico-bit/releases/latest).
3. Copy it to the `RPI-RP2` drive that appears.
4. The board reboots automatically.

On first boot, Pico Bit creates `payload.dd` with a placeholder payload if the file does not exist yet.

### 2. Use the injector

1. Plug the Pico into the target machine's USB port.
2. From another device, join the `PicoBit` Wi-Fi network.
3. Open `http://192.168.4.1` and sign in.
4. Write or load a DuckyScript payload, then click **Run**.

The payload also runs automatically at boot once the USB keyboard is ready.

### 3. Drop an agent (optional)

Agents are small programs compiled for Windows, Linux, or macOS. They collect data from the target machine and send it back to the Pico automatically.

To deploy:
1. In the portal, drag and drop an agent binary onto the **Armory** panel to upload it to the Pico.
2. Click **Copy payload** next to the binary to get the DuckyScript one-liner.
3. Run the payload — it types a download command on the target that fetches and executes the agent.
4. Results appear in the **Loot** panel once the agent reports back.

Pre-built agent binaries for Windows, Linux, and macOS are attached to each [release](https://github.com/anapeksha/pico-bit/releases/latest).

## Payload file

- The active payload is `payload.dd` on the Pico's internal filesystem
- It survives firmware updates and can be edited from the portal at any time
- The payload library stores additional named scripts under the `payloads/` directory

## Responsible use

Use Pico Bit only on systems you own or are explicitly authorized to test. Unauthorized access to computer systems is illegal.

## License

GPL-3.0-only. See `LICENSE`.
