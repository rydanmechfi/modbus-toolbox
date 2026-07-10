#!/usr/bin/env python3
"""
modbus-toolbox: read-only Modbus RTU register scanner.

For reverse-engineering register maps of undocumented Modbus RTU devices —
industrial controllers, air dryers, compressors, VFDs, cheap Chinese panel
meters — anything hanging off an RS485 bus.

STRICTLY READ-ONLY: only function codes 0x03 (read holding registers) and
0x04 (read input registers) are ever transmitted. There is deliberately no
write capability in this tool.

Only dependency: pyserial   ->   pip install pyserial

Modes
-----
discover  Find responding devices: sweeps bauds x parities x addresses.
            python modbus_scan.py discover --port COM4
dump      Dump a register range from one device to console (and CSV).
            python modbus_scan.py dump --port COM4 --baud 9600 --parity N \
                --address 1 --start 0 --count 100 --csv device_dump.csv
watch     Poll a range repeatedly, printing only registers that CHANGE.
          Run it while the target device does something (heats, pressurizes,
          cycles) — live process values reveal themselves immediately.
            python modbus_scan.py watch --port COM4 --baud 9600 --address 1 \
                --start 0 --count 60 --interval 2
"""

import argparse
import csv
import struct
import sys
import time

try:
    import serial  # pyserial
except ImportError:
    serial = None  # checked in open_port(); allows --help without pyserial


# --------------------------------------------------------------------------
# Modbus RTU framing (implemented raw so there is zero library API churn)
# --------------------------------------------------------------------------

def crc16(data: bytes) -> int:
    """Standard Modbus CRC-16 (poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def build_read_request(address: int, fc: int, start: int, count: int) -> bytes:
    pdu = struct.pack(">BBHH", address, fc, start, count)
    return pdu + struct.pack("<H", crc16(pdu))


def parse_read_response(frame: bytes, address: int, fc: int):
    """Returns ("ok", [regs]) | ("exception", code) | ("error", reason)."""
    if len(frame) < 5:
        return ("error", "short/no response")
    if struct.pack("<H", crc16(frame[:-2])) != frame[-2:]:
        return ("error", "CRC mismatch")
    if frame[0] != address:
        return ("error", f"wrong address echo {frame[0]}")
    if frame[1] == (fc | 0x80):
        return ("exception", frame[2])
    if frame[1] != fc:
        return ("error", f"unexpected function {frame[1]:#x}")
    bytecount = frame[2]
    data = frame[3:3 + bytecount]
    if len(data) != bytecount:
        return ("error", "truncated payload")
    regs = [struct.unpack(">H", data[i:i + 2])[0] for i in range(0, bytecount, 2)]
    return ("ok", regs)


def read_registers(ser, address: int, fc: int, start: int, count: int,
                   settle: float = 0.05):
    """One read transaction. Returns parse_read_response() result."""
    ser.reset_input_buffer()
    ser.write(build_read_request(address, fc, start, count))
    ser.flush()
    time.sleep(settle)
    expected = 5 + 2 * count  # addr+fc+bc + data + crc
    frame = ser.read(expected)
    # Exception frames are exactly 5 bytes; retry-read a little if short
    if len(frame) < 5:
        frame += ser.read(5 - len(frame))
    return parse_read_response(frame, address, fc)


EXCEPTION_NAMES = {
    1: "illegal function", 2: "illegal data address",
    3: "illegal data value", 4: "slave device failure",
}


def open_port(port: str, baud: int, parity: str, timeout: float):
    if serial is None:
        sys.exit("pyserial is required:  pip install pyserial")
    return serial.Serial(
        port=port, baudrate=baud, bytesize=8,
        parity={"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN,
                "O": serial.PARITY_ODD}[parity],
        stopbits=1, timeout=timeout,
    )


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------

def mode_discover(args):
    bauds = [int(b) for b in args.bauds.split(",")]
    parities = args.parities.split(",")
    addresses = range(args.first, args.last + 1)
    found = []
    print(f"Scanning {args.port}: bauds={bauds} parities={parities} "
          f"addresses={args.first}..{args.last}")
    print("(any valid-CRC reply, even an exception, means a device is there)\n")
    for baud in bauds:
        for parity in parities:
            with open_port(args.port, baud, parity, args.timeout) as ser:
                for addr in addresses:
                    for fc in (3, 4):
                        status, detail = read_registers(ser, addr, fc, 0, 1)
                        if status in ("ok", "exception"):
                            desc = (f"FC{fc:02d} reg0 -> {detail}"
                                    if status == "ok" else
                                    f"FC{fc:02d} exception: "
                                    f"{EXCEPTION_NAMES.get(detail, detail)}")
                            print(f"  FOUND addr={addr:>2}  {baud} 8{parity}1  {desc}")
                            found.append((addr, baud, parity))
                            break
                    time.sleep(args.delay)
    if not found:
        print("\nNo devices responded. Check A/B polarity (swap them — it's the "
              "#1 issue), 0/GND reference, termination, and that the "
              "device is powered.")
    else:
        combos = {(a, b, p) for a, b, p in found}
        print(f"\n{len(combos)} device/setting combination(s) found.")
        print("Next: dump each one, e.g.")
        a, b, p = found[0]
        print(f"  python modbus_scan.py dump --port {args.port} --baud {b} "
              f"--parity {p} --address {a} --start 0 --count 100")


def _dump_range(ser, address, fc, start, count, delay):
    """Read a range in chunks; fall back to single reads inside bad chunks.
    Returns {reg: value} plus a set of unreadable regs."""
    values, dead = {}, set()
    CHUNK = 8
    reg = start
    while reg < start + count:
        n = min(CHUNK, start + count - reg)
        status, detail = read_registers(ser, address, fc, reg, n)
        if status == "ok":
            for i, v in enumerate(detail):
                values[reg + i] = v
        else:
            # chunk failed -> probe registers one by one
            for r in range(reg, reg + n):
                s2, d2 = read_registers(ser, address, fc, r, 1)
                if s2 == "ok":
                    values[r] = d2[0]
                else:
                    dead.add(r)
                time.sleep(delay)
        reg += n
        time.sleep(delay)
    return values, dead


def mode_dump(args):
    with open_port(args.port, args.baud, args.parity, args.timeout) as ser:
        print(f"Dumping addr={args.address} FC{args.fc:02d} "
              f"regs {args.start}..{args.start + args.count - 1} "
              f"@ {args.baud} 8{args.parity}1\n")
        values, dead = _dump_range(ser, args.address, args.fc,
                                   args.start, args.count, args.delay)
        rows = []
        print(f"{'reg':>5} {'hex':>6} {'uint16':>7} {'int16':>7} "
              f"{'/10':>8} {'raw hex':>7}")
        for r in range(args.start, args.start + args.count):
            if r in dead:
                continue
            v = values.get(r)
            if v is None:
                continue
            s = struct.unpack(">h", struct.pack(">H", v))[0]
            print(f"{r:>5} {r:#06x} {v:>7} {s:>7} {s / 10:>8.1f} {v:#06x}")
            rows.append([r, f"{r:#06x}", v, s, s / 10])
        if dead:
            print(f"\nUnreadable registers (exception/no reply): "
                  f"{sorted(dead)}")
        if args.csv:
            with open(args.csv, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["reg_dec", "reg_hex", "uint16", "int16", "int16_div10"])
                w.writerows(rows)
            print(f"\nSaved {len(rows)} rows to {args.csv}")
        print("\nCorrelate against the device's own display/settings: process "
              "values are often x10 or x100 scaled integers.")


def mode_watch(args):
    with open_port(args.port, args.baud, args.parity, args.timeout) as ser:
        print(f"Watching addr={args.address} FC{args.fc:02d} regs "
              f"{args.start}..{args.start + args.count - 1} every "
              f"{args.interval}s — Ctrl+C to stop.")
        print("Make the device DO something and watch which registers move.\n")
        last = {}
        try:
            while True:
                values, _ = _dump_range(ser, args.address, args.fc,
                                        args.start, args.count, args.delay)
                stamp = time.strftime("%H:%M:%S")
                for r in sorted(values):
                    v = values[r]
                    if r in last and last[r] != v:
                        s = struct.unpack(">h", struct.pack(">H", v))[0]
                        print(f"[{stamp}] reg {r:>4} ({r:#06x}): "
                              f"{last[r]} -> {v}   (int16 {s}, /10 {s / 10:.1f})")
                    last[r] = v
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Read-only Modbus RTU scanner (FC03/FC04 only — never writes)")
    sub = ap.add_subparsers(dest="mode", required=True)

    def common(p):
        p.add_argument("--port", required=True, help="Serial port, e.g. COM4")
        p.add_argument("--timeout", type=float, default=0.4,
                       help="Serial read timeout seconds (default 0.4)")
        p.add_argument("--delay", type=float, default=0.2,
                       help="Delay between transactions (default 0.2s)")

    d = sub.add_parser("discover", help="sweep bauds/parities/addresses")
    common(d)
    d.add_argument("--bauds", default="9600,19200,38400",
                   help="comma list (default 9600,19200,38400)")
    d.add_argument("--parities", default="N,E", help="comma list of N,E,O")
    d.add_argument("--first", type=int, default=1)
    d.add_argument("--last", type=int, default=8,
                   help="highest address to try (default 8; max 247)")

    for name in ("dump", "watch"):
        p = sub.add_parser(name)
        common(p)
        p.add_argument("--baud", type=int, default=9600)
        p.add_argument("--parity", default="N", choices=["N", "E", "O"])
        p.add_argument("--address", type=int, required=True)
        p.add_argument("--fc", type=int, default=3, choices=[3, 4],
                       help="3=holding (default), 4=input registers")
        p.add_argument("--start", type=int, default=0)
        p.add_argument("--count", type=int, default=100)
        if name == "dump":
            p.add_argument("--csv", help="also write results to this CSV file")
        else:
            p.add_argument("--interval", type=float, default=2.0,
                           help="seconds between polls (default 2)")

    args = ap.parse_args()
    {"discover": mode_discover, "dump": mode_dump, "watch": mode_watch}[args.mode](args)


if __name__ == "__main__":
    main()
