# modbus-toolbox

Tools and field notes for poking at RS485/Modbus RTU devices whose vendors
won't give you a register map — industrial controllers, air dryers,
compressors, VFDs, panel meters, and other bus-dwelling mystery boxes.

Born out of automating a shop air-compressor system
([Shop_Assistant](https://github.com/rydanmechfi/Shop_Assistant)) where one
vendor documented their Modbus interface beautifully and the other wouldn't
hand over the protocol document at all.

## What's here

| Path | What |
|---|---|
| [`modbus_scan.py`](modbus_scan.py) | **Read-only** register scanner: discover / dump / watch |
| [`devices/`](devices/) | Register maps and notes for specific devices, one file each |

## The scanner

**Strictly read-only.** Only FC03 (read holding) and FC04 (read input) are
ever transmitted — there is deliberately no write code in the tool, so it
cannot change a setpoint on a machine you don't understand yet.

Zero-churn design: Modbus RTU framing and CRC16 are implemented raw over
pyserial, so there's no Modbus-library API drift to fight.

### Install

```
pip install pyserial
```

### 1. `discover` — who's on the bus?

Sweeps bauds × parities × addresses. Any valid-CRC reply — even a Modbus
exception — proves a device is listening with those settings.

```
python modbus_scan.py discover --port COM4
python modbus_scan.py discover --port COM4 --bauds 9600,19200,38400,57600,115200 --last 32
```

### 2. `dump` — read everything

Dumps a register range as a table showing each value as unsigned, signed,
and ÷10 (the most common scaling), with optional CSV output. Chunked reads
with per-register fallback, so one unreadable register doesn't blank a
whole block.

```
python modbus_scan.py dump --port COM4 --baud 9600 --parity N --address 1 --start 0 --count 100 --csv dump.csv
python modbus_scan.py dump --port COM4 --address 1 --fc 4 --start 0 --count 100   # input registers
```

### 3. `watch` — find the live values

Polls repeatedly and prints **only registers that change**. This is the
fastest way to identify process values: make the machine do something
(pressurize, heat up, cycle) and the relevant registers announce themselves.

```
python modbus_scan.py watch --port COM4 --baud 9600 --address 1 --start 0 --count 60 --interval 2
```

## Correlation technique

1. Dump the register space while the device is idle.
2. Read the device's own display/menus and note every number it shows you
   (temperatures, pressures, hour counters, setpoints).
3. Hunt those numbers in the dump — try raw, ×10, and ×100
   (`7.5 bar` → look for `75` or `750`).
4. Run `watch` while the machine works; changing registers = live telemetry.
5. Setpoints usually sit near each other in a writable block; hour counters
   are large numbers that only tick up; status words are small integers or
   bitfields that flip with the machine's state.

## Hardware

Reference adapter: **Waveshare USB TO RS232/485/TTL** (FT232RL, automatic
TX/RX direction control, TVS/fuse protected). RS485 screw terminals:
**A+ / B− / GND**. Shows up on Windows as *USB Serial Port (COMx)*.
Any FTDI/CH340-based RS485 adapter works.

### Wiring crib sheet

- Adapter **A → device A/D+**, **B → device B/D−**. Labels lie: if nothing
  responds, **swap A and B first** — it's the #1 cause of silence.
- Common ground helps on flaky links: adapter GND → device 0/GND/COM.
- Bench-scan point-to-point before trusting a multidrop bus.
- Permanent buses: twisted pair (22 AWG shielded), shield grounded at ONE
  end only, 120 Ω termination at the two physical ends, no star topology,
  keep away from motor/VFD cabling.

## Etiquette for unknown devices

- Reads are safe; **never write** to a device whose map you don't know.
- Some devices dislike fast polling — if replies are flaky, raise `--delay`
  (one dryer in `devices/` requires >500 ms between transactions).
- Devices that write parameters to EEPROM can be worn out by repeated
  writes; another reason this tool doesn't have any.

## devices/

One markdown file per device: comm parameters, register map (confirmed or
suspected), scaling, quirks. PRs-to-self welcome. Current inventory:

- [`vevor-tr02-tr03-air-dryer.md`](devices/vevor-tr02-tr03-air-dryer.md) —
  fully documented (from OEM manual)
- [`logika-logik-26s.md`](devices/logika-logik-26s.md) — scan pending;
  everything known so far

## License

MIT — see [LICENSE](LICENSE).
