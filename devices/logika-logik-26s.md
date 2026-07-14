# LogikaControl Logik 26-S (screw compressor controller)

Status: **partially mapped — live scan 2026-07-12.** Working pressure, airend
temperature, machine status, load flag, and the working/load hour counters are
now confirmed by correlation against the panel during a real load cycle.
Logika's separate "MODBUS protocol communication" document was never obtained —
this map was reverse-engineered read-only. See **Findings** below.

## Known facts (comms — CONFIRMED on the bench 2026-07-12)

| Item | Value |
|---|---|
| Ports | **M2 "RS485 BASE"** = external comms (used this one). M8 = Danfoss inverter only — do not use. |
| M2 pinout | pole 1 = 0 (GND), pole 2 = D−, pole 3 = D+, pole 4 = +15 Vdc out (**do not connect pole 4**) |
| Wiring used | adapter D+ → M2 pole 3, D− → M2 pole 2, GND → M2 pole 1 |
| Slave address | Parameter **C08 "Compressor Nr"** (menu 04, password level 1 = `22`); set to **2** on this unit → **confirmed responding at address 2** |
| Baud/parity | **Confirmed 9600 8N1** (same as the Vevor dryer) |
| Function codes | **FC03 (read holding) works.** FC04 (input registers) returns an exception across the whole space — **not supported.** No writes attempted (read-only tool). |
| Watchdog | Alarm 33 (RS485 watchdog) did **not** trigger — it only arms when serial start/stop control is enabled, which we never enable. |
| Bus rules | Max 32 units, 400 m, 22 AWG shielded twisted, shield grounded one end, 120 Ω termination both ends |

## Register-space layout notes

- Data lives in **128-register pages** (populated bases seen: 0x000, 0x080,
  0x100, 0x300, 0x400, 0x500, 0x600, 0x800, 0xB00, 0x1000…). Reading past the
  end of a populated block returns an "illegal data address" exception.
- **Many pages are mirrored** at +0x80 (0x100↔0x180, 0x300↔0x380, 0x400↔0x480,
  0x500↔0x580). Read the canonical (lower) copy.
- Live telemetry sits in the **0x400 page (dec 1024+)**; the hour counters sit
  in the **0x600 page (dec 1536+)**.

## Findings — confirmed registers (addr 2, 9600 8N1, FC03 holding)

| Reg dec | Reg hex | Meaning | Scaling | How confirmed |
|---|---|---|---|---|
| **1027** | 0x0403 | **Machine status / state** | enum (below) | tracked through a full off→start→load→cutout→unload cycle |
| **1029** | 0x0405 | **Airend / oil temperature** | **÷10 = °C** | cooldown + heat-up curves; reg=790 matched panel 174.2 °F (79.0 °C) |
| **1030** | 0x0406 | **Working (line) pressure** | **÷10 = bar** (reg × 1.45 = psi) | 6-point correlation vs the gauge across an 88→145 psi build |
| **1037** | 0x040d | **Load / compressing flag** | 1000 = loaded, 0 = unloaded | 0→1000 at load start, 1000→0 at 145 psi cutout |
| **1536–1537** | 0x0600–0x0601 | **Working time** | **32-bit, minutes** (÷60 = hours), high word 1536 / low word 1537 | 50273 min = 837.9 h ≈ panel **837 working hours**; +1/min while running |
| **1538–1539** | 0x0602–0x0603 | **Load time** | **32-bit, minutes** (÷60 = hours), high word 1538 / low word 1539 | 31917 min = 531.9 h ≈ panel **531 load hours** |

> ⚠️ **Read the hour counters as a block starting at the pair base (1536 /
> 1538).** Single-register FC03 reads of 1537 or 1539 alone return 0 —
> confirmed live 2026-07-13 with ESPHome polling. A 2-register read from 1536
> (U_DWORD, high word first) returns the correct value, verified against the
> panel: 838.2 h working / 532.1 h load. The scanner never tripped on this
> because `dump` always reads whole blocks from the 0x600 base.

### reg1027 status enum (observed)

| Value | State |
|---|---|
| 0 | Off / standby |
| 5 | Starting |
| 11 | Running, loaded |
| 19 | Running, unloaded |
| 27 | Cutout transition (unloading at upper setpoint) |

### reg1030 pressure correlation (the confirming evidence)

| Gauge (psi) | reg1030 | ÷10 (bar) | bar → psi check |
|---|---|---|---|
| 88 | 60–61 | 6.0–6.1 | 6.07 bar = 88 psi ✓ |
| ~93 | 64 | 6.4 | 92.8 psi ✓ |
| ~99 | 68 | 6.8 | 98.6 psi ✓ |
| 105 | 72 | 7.2 | 104.4 psi ✓ |
| 115 | 79 | 7.9 | 114.6 psi ✓ |
| 125 | 86 | 8.6 | 124.7 psi ✓ |
| 145 (cutout) | 100 | 10.0 | 145.0 psi ✓ |

### Maintenance service intervals (0x500 config page)

The service **setpoints** are stored; the panel "count" (hours remaining) is
**computed, not stored** — it equals `setpoint − working_hours`, which is why
CAF/COF read 2162 (= 3000 − 838) and CSF reads 5162 (= 6000 − 838) at 838
working hours.

Item names confirmed 2026-07-13 against the EMAX PRS0100001 manual's
"Maintenance Notifications" table, which lists the components in the same
order as the panel menu:

| Reg dec | Reg hex | Programmed value | Item (per EMAX manual) | EMAX manual lifetime |
|---|---|---|---|---|
| 1312 | 0x0520 | 3000 | **CAF** air filter | 4000 h |
| 1313 | 0x0521 | 3000 | **COF** oil filter | 4000 h |
| 1314 | 0x0522 | 6000 | **CSF** air/oil separator filter | 4000 h |
| 1315 | 0x0523 | 3000 | **C--=** lubricating oil | 4000 h |
| 1316 | 0x0524 | 3000 | **C--h** check compressor | 4000 h |
| 1317 | 0x0525 | 29999 | **BL** motor bearing grease | 10000 h |

> ⚠️ The values programmed into the Logik (3000/3000/6000/3000/3000/29999 —
> apparently Logika defaults) do **not** match the EMAX manual's schedule
> (4000 ×5, 10000). The panel will raise its service nags on the programmed
> values, first at 3000 h, unless they are edited on the panel.

To compute remaining hours: `setpoint(reg1312/1313/1314) − working_hours
(reg1537 ÷ 60)`. This is exact until an item is **reset** on the panel; after a
reset the per-item elapsed baseline (currently 0, since none have been reset)
diverges from total working hours. That baseline register is currently 0 and
so not yet identifiable — it can be found by watching for the register that
jumps 0 → ~(working hours) during a live maintenance reset.

## Suspected / unresolved (leads, NOT confirmed)

- **1024, 1025, 1026** — small integers that wobble with machine state; likely
  digital output/status bits (fan, load solenoid, etc.). Not decoded.
- **1028 = 2095**, **1032 = 3298** — static during the whole run; config
  constants (motor rpm? model code?). Unknown.
- **1033 ≈ 175–187** (÷10 = 17.5–18.7) — possibly inlet/ambient air temp (°C).
  Wobbles; not confirmed.
- **1034** — packed status word (0x0100 / 0x0F01 / 0x0D01 / 0x0D21); changes at
  load/unload. Bitfield, not decoded.
- **1541, 1543, 1545, 1547, 1549** — mirror the working-minutes value (1537).
- **Maintenance "count" (2162 / 5162 h) is not a stored register** — resolved:
  it is `setpoint − working_hours` computed by the panel (see the Maintenance
  section above). Only the setpoints (1312–1317) and working hours (1537) are
  stored.
- **Per-item maintenance reset baselines** — presumed to exist (one per service
  item) but all read 0 (nothing reset yet), so not yet identifiable. Capture by
  watching a live panel reset.

## Values still worth hunting (visible on the LCD for correlation)

- Internal pressure P2 (if aux transducer fitted)
- Start/stop setpoints WP3 (stop) / WP4 (start)
- Starts-per-hour, and the maintenance countdowns CAF / COF / CSF / C-- / C--h /
  C-BL (the oil-hours family)
- Alarm codes AL01–AL62

## Scan procedure

See the full write-up in
[Shop_Assistant/docs/COMPRESSOR_MODBUS_SCAN.md](https://github.com/rydanmechfi/Shop_Assistant/blob/main/docs/COMPRESSOR_MODBUS_SCAN.md).
On macOS the adapter enumerates as `/dev/cu.usbserial-XXXX` (use `cu.*`, not
`tty.*`). What worked here:

```
python modbus_scan.py discover --port /dev/cu.usbserial-BG01097T
python modbus_scan.py dump  --port /dev/cu.usbserial-BG01097T --baud 9600 --parity N --address 2 --start 1024 --count 14
python modbus_scan.py watch --port /dev/cu.usbserial-BG01097T --baud 9600 --address 2 --start 1024 --count 14 --interval 2
```

The decisive move was **`watch` during an actual load cycle**: pressure is a
*static* register while the machine sits idle (so it never appears in a
change-only watch). Draining the tank to 88 psi and letting it pump back up to
the 145 psi cutout made reg1030 sweep 60→100 and reveal itself, with airend
temp (1029) and status (1027) moving alongside as positive controls.

**Read-only.** Never write to this controller — setpoint registers are
writable on similar controllers and a wrong write could alter compressor
protection settings.
