"""
End-to-end BLE check against a Nova-Band running the firmware (Windows/macOS/Linux).

    python tools/ble_test.py

Scans for "NovaBand-*", subscribes to telemetry, the PPG wave and the
standard Heart Rate Measurement, then plays the app's part: hello (profile +
time), a coach message, run start, run stop. Prints what comes back.
"""
import asyncio
import json
import time

from bleak import BleakClient, BleakScanner

SVC = "4e420001-6e6f-7661-6261-6e6453330000"
TELEM = "4e420002-6e6f-7661-6261-6e6453330000"
WAVE = "4e420003-6e6f-7661-6261-6e6453330000"
CMD = "4e420004-6e6f-7661-6261-6e6453330000"
HRM = "00002a37-0000-1000-8000-00805f9b34fb"


async def main():
    print("scanning ...")
    dev = await BleakScanner.find_device_by_filter(lambda d, ad: (d.name or "").startswith("NovaBand"), timeout=15)
    if not dev:
        print("no NovaBand found")
        return
    print("found", dev.name, dev.address)
    stats = {"telem": 0, "wave": 0, "hr": 0}
    async with BleakClient(dev) as c:
        print("connected, mtu", c.mtu_size)

        def on_telem(_, data):
            stats["telem"] += 1
            print("  telem", data.decode(errors="replace"))

        def on_wave(_, data):
            stats["wave"] += 1

        def on_hr(_, data):
            stats["hr"] += 1

        await c.start_notify(TELEM, on_telem)
        await c.start_notify(WAVE, on_wave)
        await c.start_notify(HRM, on_hr)

        async def send(obj):
            await c.write_gatt_char(CMD, json.dumps(obj, separators=(",", ":")).encode(), response=True)
            print(">", obj)

        await send({"cmd": "hello", "name": "Tester", "age": 17, "alert": 190, "t": int(time.time()), "tz": 420})
        await asyncio.sleep(3)
        await send({"cmd": "msg", "text": "BLE test from laptop", "level": "good"})
        await asyncio.sleep(3)
        await send({"cmd": "run", "a": "start"})
        await asyncio.sleep(5)
        await send({"cmd": "run", "a": "stop"})
        await asyncio.sleep(2)
        await send({"cmd": "page", "i": 0})
        await asyncio.sleep(1)
    print("received:", stats)


asyncio.run(main())
