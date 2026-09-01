#!/usr/bin/env python3
"""
Logitech G815 M-Key LED Off

Turns off the yellow M1/M2/M3 indicator LEDs on a Logitech G815
by using Logitech HID++ directly.

Dependency:
    py -m pip install hidapi

Run:
    py g815_mkeys_off.py
"""

import time
import hid

VID = 0x046D
PID = 0xC33F

REPORT_ID = 0x11
DEVICE_INDEX = 0xFF
SOFTWARE_ID = 0x0D

FEATURE_MKEYS = 0x8020


def make_packet(feature_index, function, payload=b""):
    fn_sw = (function & 0xF0) | SOFTWARE_ID
    packet = bytes([
        REPORT_ID,
        DEVICE_INDEX,
        feature_index,
        fn_sw,
    ]) + payload
    return packet.ljust(20, b"\x00")


def drain(dev):
    dev.set_nonblocking(True)
    while dev.read(64):
        pass
    dev.set_nonblocking(False)


def transact(dev, feature_index, function, payload=b"", timeout_ms=700):
    drain(dev)

    packet = make_packet(feature_index, function, payload)
    if dev.write(packet) != 20:
        raise RuntimeError("Failed to write HID++ packet.")

    wanted_fn = (function & 0xF0) | SOFTWARE_ID
    deadline = time.monotonic() + timeout_ms / 1000.0

    while time.monotonic() < deadline:
        remaining = max(1, int((deadline - time.monotonic()) * 1000))
        data = dev.read(64, remaining)

        if not data:
            continue

        data = bytes(data)

        if (
            len(data) >= 4
            and data[0] == REPORT_ID
            and data[1] == DEVICE_INDEX
            and data[2] == feature_index
            and data[3] == wanted_fn
        ):
            return data

    raise RuntimeError("Keyboard did not acknowledge HID++ command.")


def lookup_feature(dev, feature_id):
    response = transact(
        dev,
        0x00,                  # HID++ ROOT feature
        0x00,                  # GetFeature
        feature_id.to_bytes(2, "big"),
    )

    feature_index = response[4]

    if feature_index == 0:
        raise RuntimeError(
            f"Keyboard does not expose HID++ feature 0x{feature_id:04X}."
        )

    return feature_index


def find_hidpp_interface():
    for info in hid.enumerate(VID, PID):
        dev = hid.device()

        try:
            dev.open_path(info["path"])
            dev.set_nonblocking(False)

            # If this succeeds, this is the HID++ interface.
            mkeys_index = lookup_feature(dev, FEATURE_MKEYS)
            return dev, mkeys_index

        except Exception:
            try:
                dev.close()
            except Exception:
                pass

    raise RuntimeError(
        "G815 found, but no HID++ interface responded."
    )


def main():
    dev = None

    try:
        dev, mkeys_index = find_hidpp_interface()

        # HID++ feature 0x8020, function 0x10:
        # bit 0 = M1
        # bit 1 = M2
        # bit 2 = M3
        #
        # 0x00 = all M-key LEDs off
        transact(dev, mkeys_index, 0x10, b"\x00")

        print("G815 M1/M2/M3 LEDs: OFF")

    except Exception as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)

    finally:
        if dev is not None:
            try:
                dev.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
