"""Exercise the bundled ARM64 APK in Google's ARM-translating Android emulator."""
import re
import struct
import subprocess
import time
import xml.etree.ElementTree as ET


def adb(*args):
    return subprocess.check_output(["adb", *args], text=True, timeout=45).strip()


def screen():
    adb("shell", "uiautomator", "dump", "/sdcard/frankesso-test.xml")
    return list(ET.fromstring(adb("shell", "cat", "/sdcard/frankesso-test.xml")).iter("node"))


def wait_for(check, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        nodes = screen()
        result = check(nodes)
        if result is not None:
            return result
        time.sleep(1)
    raise RuntimeError("Expected app state was not reached. Screen: " +
                       repr([n.get("text") for n in nodes if n.get("text")]))


def find(nodes, predicate):
    return next((n for n in nodes if predicate(n)), None)


def tap(n):
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


wait_for(lambda nodes: find(nodes, lambda n: n.get("text") == "Ready."), 150)
print("Fresh bundled model prepared and opened in Android while offline.", flush=True)


def assert_system_palette(expected):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        raw = subprocess.check_output(["adb", "exec-out", "screencap"], timeout=15)
        width, height, pixel_format = struct.unpack_from("<III", raw)
        if pixel_format not in (1, 2) or len(raw) < width * height * 4 + 12:
            raise RuntimeError("Expected RGBA/RGBX emulator screenshot.")
        pixels = raw[-width * height * 4:]
        sampled = [pixels[i:i + 3] for i in range(0, len(pixels), 404)]
        if sum(value == bytes(expected) for value in sampled) > len(sampled) // 2:
            return
        time.sleep(0.5)
    raise RuntimeError(f"App screen did not adopt the system palette {expected}.")


assert all(n.get("content-desc") != "Settings" and n.get("text") != "Settings" for n in screen())


def ask(query):
    tap(wait_for(lambda nodes: find(nodes, lambda n: n.get("class") == "android.widget.EditText"), 15))
    adb("shell", "input", "text", query.replace(" ", "%s"))
    tap(wait_for(lambda nodes: find(nodes, lambda n: n.get("text") == "Send" and n.get("enabled") == "true"), 15))


ask("test")
signal = "Signal received from the other side. Something knocked back. ☕"
wait_for(lambda nodes: find(nodes, lambda n: signal in n.get("text", "")), 15)
adb("shell", "cmd", "uimode", "night", "yes")
assert_system_palette((10, 9, 9))
wait_for(lambda nodes: find(nodes, lambda n: signal in n.get("text", "")), 15)
adb("shell", "cmd", "uimode", "night", "no")
assert_system_palette((250, 242, 228))
wait_for(lambda nodes: find(nodes, lambda n: signal in n.get("text", "")), 15)
tap(wait_for(lambda nodes: find(nodes, lambda n: n.get("text") == "New chat" and n.get("enabled") == "true"), 15))
wait_for(lambda nodes: True if all(signal not in n.get("text", "") for n in nodes) else None, 15)
ask("Name a flower.")
started = time.monotonic()


def completed(nodes):
    texts = [n.get("text", "") for n in nodes]
    errors = ("Couldn’t generate", "Reply stopped at", "No reply.")
    if any(t.startswith(errors) for t in texts):
        raise RuntimeError("Offline generation did not complete: " + repr(texts))
    if "Ready." in texts:
        for t in texts:
            if "Name a flower." in t and "Frankesso\n" in t and t.rsplit("Frankesso\n", 1)[-1].strip():
                return True


wait_for(completed, 90)
print(f"Bundled ARM64 APK returned a real offline reply in {time.monotonic() - started:.1f}s (including UI polling).")


for query, response in (
    ("What is your favourite colour", "Crimson. It’s the only color that makes it through the portal intact."),
    ("favorite food or drink", "Coffee."),
    ("favorite drug", "Caffeine."),
    ("favorite weather", "Fog."),
    ("biggest pet peeve", "Decaf."),
    ("Where are you from", "The side of the mirror that stays warm."),
    ("favorite time of day", "Night."),
    ("favorite clock time", "Midnight."),
):
    ask(query)
    wait_for(lambda nodes: find(nodes, lambda n: (
        f"{query}\n\nFrankesso\n{response}" in n.get("text", ""))), 15)
print("All eight deterministic persona replies work in Android with radios disabled.")
