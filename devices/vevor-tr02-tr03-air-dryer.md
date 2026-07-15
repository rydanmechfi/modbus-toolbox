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
  F21 = 180 s anti-short-cycle — safe to switch reg 16 remotely.
- ⚠️ **Register 16 writes are gated by F60 "System control mode"** (0 = Local
  control [factory default], 1 = Remote control) — confirmed against the OEM
  manual (now in `Shop_Assistant/equipment-manuals/Vevor Air Dryer
  English.pdf`, §6.2/parameter table) and live on the bench 2026-07-14: with
  F60 at its default of 0, every FC06 write to reg 16 is rejected with
  **Modbus exception 3 (illegal data value)** — reads to every other register
  work fine throughout, so this looked like a wiring fault before the manual
  surfaced it. **Set F60 = 1 on the panel before attempting to control power
  via Modbus.**
- **F58 "Remote switch type"** (default 1 = normally closed) governs the S1
  terminal (see wiring diagram, §7: S1 = "Remote switch (RED)"), and per the
  manual is "invalid when F60 is set to local control" — implying S1 only
  matters once F60 = 1. Unconfirmed whether S1 must *also* be satisfied
  (e.g. jumpered closed) for reg-16 writes to hold once F60 = 1, or whether
  Modbus alone is sufficient — test F60 = 1 alone first before wiring S1.
- Front-panel alarm codes (A11 pressure, A21/A22 sensor, A31 dew point,
  A32 condensation) surface in the reg 7 bitfield.
- ESPHome integration example (modbus_controller with
  `command_throttle: 600ms`): see
  [Shop_Assistant/shop-controller.yaml](https://github.com/rydanmechfi/Shop_Assistant/blob/main/shop-controller.yaml).
