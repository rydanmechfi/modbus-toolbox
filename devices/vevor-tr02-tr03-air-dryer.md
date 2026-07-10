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

Temperature resolution is 0.1° — expect ×10 integers. Panel °C/°F setting
may affect the reported unit; verify against the display.

## Behavior notes

- Compressor has built-in protection: F20 = 60 s power-on start delay,
  F21 = 180 s anti-short-cycle — safe to switch reg 16 remotely.
- Front-panel alarm codes (A11 pressure, A21/A22 sensor, A31 dew point,
  A32 condensation) surface in the reg 7 bitfield.
- ESPHome integration example (modbus_controller with
  `command_throttle: 600ms`): see
  [Shop_Assistant/shop-controller.yaml](https://github.com/rydanmechfi/Shop_Assistant/blob/main/shop-controller.yaml).
