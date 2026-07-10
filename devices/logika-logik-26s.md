# LogikaControl Logik 26-S (screw compressor controller)

Status: **register map unknown — scan pending.** Logika's separate
"MODBUS protocol communication" document proved unobtainable. This file
collects everything known so far; scan results go here when captured.

## Known facts (from the Logik 26-S user manual, Rev 1 2015)

| Item | Value |
|---|---|
| Ports | **M2 "RS485 BASE"** = external comms (use this one). M8 = Danfoss inverter only — do not use. |
| M2 pinout | pole 1 = 0, pole 2 = D−, pole 3 = D+, pole 4 = +15 Vdc out |
| Slave address | Parameter **C08 "Compressor Nr"** (1–32, default **1**), menu 04, password level 1 = `22` |
| Baud/parity | **Not stated** — scan 9600/19200/38400 × N/E |
| Protocol | Manual references "MODBUS protocol communication" and a serial start/stop watchdog (alarm 33), so a Modbus RTU slave mode exists |
| Bus rules | Max 32 units, 400 m, 22 AWG shielded twisted, shield grounded one end, 120 Ω termination both ends |

## Values worth hunting (visible on the LCD for correlation)

- Working pressure P1 (big digits; setpoints WP3 stop / WP4 start nearby)
- Internal pressure P2 (if aux transducer fitted)
- Airend temperature
- Working hours / load hours / starts-per-hour (menu 01 Info)
- Maintenance countdowns: CAF / COF / CSF / C-- / C--h / C-BL
- Status (Off / waiting / running / load / unload) and alarm codes AL01–AL62

## Scan procedure

See the full write-up in
[Shop_Assistant/docs/COMPRESSOR_MODBUS_SCAN.md](https://github.com/rydanmechfi/Shop_Assistant/blob/main/docs/COMPRESSOR_MODBUS_SCAN.md).
Short version: validate the adapter against a known-good device, then

```
python modbus_scan.py discover --port COM4
python modbus_scan.py dump --port COM4 --baud <found> --parity <found> --address <C08> --start 0 --count 100 --csv logik_dump.csv
python modbus_scan.py watch --port COM4 --baud <found> --address <C08> --start 0 --count 60
```

**Read-only.** Never write to this controller — setpoint registers are
writable on similar controllers and a wrong write could alter compressor
protection settings.

## Findings

*(empty — paste discover/dump/watch results here as they're captured)*
