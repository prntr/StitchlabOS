# SKR Pico Firmware

Seed configs for the MCU firmware that ships inside the StitchLabOS image.

CI builds these into `stitchlabos/image/src/modules/pico-firmware/filesystem/home/pi/firmware/`
before the image build runs, and the `pico-firmware` module refuses to build an
image whose firmware is missing. The binaries themselves are never committed —
see `.gitignore`.

## Why this exists

A factory-fresh SKR Pico holds no Klipper firmware. Before this, commissioning a
machine required building firmware on a separate computer with internet access,
because the image deliberately omits the ~700 MB ARM toolchain and a Pi in AP
mode has no network. That made "flash the SD card and go" impossible.

## The three builds

| Seed | Output | Where it goes |
|---|---|---|
| `skr-pico/katapult.config` | `katapult.uf2` | Bootloader at `0x10000100`, written once over USB BOOTSEL |
| `skr-pico/klipper.config` | `klipper.bin`, `klipper.uf2` | Application at `0x10004000`, written through Katapult over `/dev/serial0` |
| `skr-pico/klipper-standalone.config` | `klipper-standalone.uf2` | Application at `0x10000100`, no bootloader — rescue only |

`klipper.uf2` and `klipper-standalone.uf2` are **not interchangeable**. The first
starts at `0x10004000` and needs Katapult below it to be reachable at all; drop
it onto a bare board over BOOTSEL and nothing boots. The standalone build is the
one to use when Katapult is gone, at the cost of needing BOOTSEL for every future
update.

## The contract these files encode

```text
Pi GPIO14 (TXD) ──► Pico GPIO1 (UART0 RX)
Pi GPIO15 (RXD) ──► Pico GPIO0 (UART0 TX)
115200 baud
```

The baud rate must equal `baud:` under `[mcu]` in
[`printer.cfg`](../stitchlabos/image/src/modules/klipper/filesystem/home/pi/printer_data/config/printer.cfg).
Klipper's own default is 250000, so leaving `CONFIG_SERIAL_BAUD` out would
produce firmware that builds cleanly and then never answers.

The full board pinout, including the clash between this UART and the Hybrid
encoder's documented I2C pins, is kept in
`~/Code/active/wissen/electronics/skr-pico-v1.md`.

## Changing a config

Edit the seed, never a generated `.config`. CI runs `make olddefconfig` and then
asserts that every non-comment line of the seed survived — if upstream renames a
symbol, the build fails with the offending line instead of shipping mute
firmware.

That check earns its keep: upstream has already moved these symbols from the
`RP2040_*` / `MACH_RP2040` naming that older notes use to the current
`RPXXXX_*` / `MACH_RPXXXX` family. The flash addresses did not change.

To verify a symbol before changing a seed:

```bash
curl -s https://raw.githubusercontent.com/Klipper3d/klipper/master/src/rp2040/Kconfig
```

## Flashing

On the machine itself:

```bash
ssh pi@stitchlab.local
stitchlab-flash-pico
```

See [docs/11-commissioning.md](../docs/11-commissioning.md) for the full
commissioning walkthrough and the recovery paths.
