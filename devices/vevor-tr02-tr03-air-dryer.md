# Vevor TR-02 / TR-03 Refrigerated Air Dryer

Controller: **RDC-21-01/-02** (a.k.a. **DS8011**) — panel-mount temperature
controller with RS485. Register map is **fully documented** in the OEM manual
("Freezing Drying Machine TR-02/TR-03", §6 Remote communication), reproduced
here.

## Comm parameters

| Item | Value |
|---|---|
| Physical | RS485, terminals A / B (+ V/G on the 4-pin header) |
| Protocol | Modbus RTU, slave |
| Serial | **9600 baud, 8 data, no parity, 1 stop** |
| Function codes | **FC03 (read) and FC06 (write single) only** |
| Slave address | Parameter **F91**, factory default **1** |
| Poll rate | Master interval **must exceed 500 ms** |
| Writes | Flash EEPROM — write only on change, never poll-write |

Panel access: hold **SET** 3 s → `PAS` → password (param F90, default **55**).

## Register map (decimal addresses)

| Reg | Hex | Access | Contents |
|---|---|---|---|
| 0 | 0x0000 | R | Dew point temperature |
| 1 | 0x0001 | R | Condensation temperature |
| 2–3 | | R | Reserved (0) |
| 4 | 0x0004 | R | Digital input status — b1 remote switch, b2 fault signal |
| 5 | 0x0005 | R | Digital output status — b0 compressor relay, b1 fan relay, b2 alarm relay, b8 compressor waiting |
| 6 | 0x0006 | R | Controller status — b0 power on, b1 shutdown, b2 working, b3 alarm |
| 7 | 0x0007 | R | Alarm status 1 — b0 dew-point sensor fault, b1 condensation sensor fault, b4 dew-point high alarm, b6 condensation high alarm, b8 external fault |
| 8 | 0x0008 | R | Alarm status 2 — b0 memory failure |
| 9 | 0x0009 | R | Software version (10 = V1.0) |
| 10 | 0x000A | R | Compressor accumulated run time (hours) |
| 11–15 | | R | Reserved (0) |
| 16 | 0x0010 | **R/W** | **On/Off — write 1 = on, 0 = off** |
| 17–51 | 0x0011–0x0033 | R/W | System parameters (F11…F91) — register↔parameter order not explicitly documented; verify before writing |

## Scaling

**Confirmed live 2026-07-13:** temperatures arrive as whole-degree integers in
the **panel's display unit** — this unit is set to °F and reg 0 read 37 (37 °F
dew point), reg 1 read 118 (118 °F condenser), matching the display. No ×10
scaling was observed despite the manual's "0.1° resolution" note. If the panel
is switched to °C, expect the registers to follow.

## Behavior notes

- Compressor has built-in protection: F20 = 60 s power-on start delay,
  F21 = 180 s anti-short-cycle.
- **Register 16 writes require F60 "System control mode" = 1 (Remote
  control)** — factory default is 0 (Local control), documented in the OEM
  manual (`Shop_Assistant/equipment-manuals/Vevor Air Dryer English.pdf`,
  §6.2/parameter table). Set this on the panel before attempting to control
  power via Modbus at all.
- ⚠️ **The real root cause of a long "on writes always fail, off writes
  always work" debugging session (2026-07-14/15) turned out to be on the
  ESPHome side, not the dryer.** ESPHome's `modbus_controller` switch writes
  `state ? 0xFFFF & bitmask : 0` for FC06, and defaults `bitmask` to
  `0xFFFFFFFF` when unset — so a switch on this register with **no explicit
  `bitmask` wrote the literal value 65535 for "on"**, which the dryer
  correctly rejected as out of range (**Modbus exception 3**) for a register
  documented to accept only 0/1. "Off" (a real `0`) always succeeded, which
  is what made this look like a device-side permission problem for so long.
  **Any switch on this register needs `bitmask: 0x0001` explicitly set** —
  see the fix in
  [Shop_Assistant/shop-controller.yaml](https://github.com/rydanmechfi/Shop_Assistant/blob/main/shop-controller.yaml).
- Ruled out along the way, kept here so it isn't re-investigated: **F58
  "Remote switch type" and the S1 terminal do not gate reg-16 writes** —
  tested with S1 both unwired and physically jumpered closed, under both
  F58 = 1 (NC) and F58 = 0 (NO); no combination changed the outcome once the
  bitmask bug above was the actual blocker. The panel's own local shutdown
  toggle (hold ∨+∧ 3 s, §4.4) was also checked and isn't the cause either.
- Front-panel alarm codes (A11 pressure, A21/A22 sensor, A31 dew point,
  A32 condensation) surface in the reg 7 bitfield.
- ESPHome integration example (modbus_controller with
  `command_throttle: 600ms`): see
  [Shop_Assistant/shop-controller.yaml](https://github.com/rydanmechfi/Shop_Assistant/blob/main/shop-controller.yaml).
