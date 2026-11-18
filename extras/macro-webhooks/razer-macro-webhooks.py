#!/usr/bin/env python3
"""
razer-macro-webhooks - fire a webhook when a Razer macro key is pressed.

Runs as a system service, so it keeps working at the login screen and with nobody
logged in (desktop keyboard shortcuts only exist inside a logged-in session).

Usage:
    razer-macro-webhooks.py [--config PATH] [--dry-run]

The config (JSON, default /etc/razer-macro-webhooks.json) maps evdev key names to URLs:
    {
      "KEY_F18": "http://homeassistant.local:8123/api/webhook/YOUR_ID",
      "KEY_F17": {"url": "http://homeassistant.local:8123/api/webhook/OTHER_ID", "method": "POST"}
    }
On a BlackWidow V4 X the macro keys M1 to M6 send KEY_F13 to KEY_F18.
--dry-run prints the key presses it sees instead of sending anything.
"""

import argparse
import json
import selectors
import sys
import threading
import time
import urllib.request

from evdev import InputDevice, ecodes, list_devices

DEFAULT_CONFIG = "/etc/razer-macro-webhooks.json"
RESCAN_SECONDS = 5        # how often to look for newly plugged-in keyboards
DEBOUNCE_SECONDS = 0.4    # one press can be reported by more than one input device
REQUEST_TIMEOUT = 5
METHODS = ("POST", "PUT", "GET")


def load_config(path):
    try:
        with open(path) as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit(f"Cannot read config {path}: {e}")
    if not isinstance(raw, dict) or not raw:
        raise SystemExit(f"Config {path} must be a non-empty JSON object")
    hooks = {}
    for name, spec in raw.items():
        code = ecodes.ecodes.get(name)
        if code is None:
            raise SystemExit(f"Config {path}: unknown key name {name!r}")
        if isinstance(spec, str):
            spec = {"url": spec}
        if not isinstance(spec, dict):
            raise SystemExit(f"Config {path}: {name} must be a URL or an object with a 'url'")
        url = spec.get("url", "")
        method = str(spec.get("method", "POST")).upper()
        if not (isinstance(url, str) and url.startswith(("http://", "https://"))):
            raise SystemExit(f"Config {path}: {name} needs an http:// or https:// url")
        if method not in METHODS:
            raise SystemExit(f"Config {path}: {name} method must be one of {', '.join(METHODS)}")
        hooks[code] = {"name": name, "url": url, "method": method}
    return hooks


def fire(hook, dry_run):
    if dry_run:
        print(f"{hook['name']} pressed (dry run, nothing sent)", flush=True)
        return
    data = b"" if hook["method"] in ("POST", "PUT") else None
    req = urllib.request.Request(hook["url"], data=data, method=hook["method"])
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            print(f"{hook['name']}: {hook['method']} -> HTTP {resp.status}", flush=True)
    except Exception as e:   # the URL is deliberately not logged: it contains the webhook ID
        print(f"{hook['name']}: request failed ({type(e).__name__}: {e})", file=sys.stderr, flush=True)


def main():
    ap = argparse.ArgumentParser(description="Fire webhooks from Razer macro keys.")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help=f"config file (default {DEFAULT_CONFIG})")
    ap.add_argument("--dry-run", action="store_true", help="print key presses instead of sending requests")
    args = ap.parse_args()

    hooks = load_config(args.config)
    sel = selectors.DefaultSelector()
    seen = set()          # input device paths already examined
    last_fire = {}        # key code -> time of last accepted press
    last_scan = 0.0

    while True:
        now = time.monotonic()
        if now - last_scan >= RESCAN_SECONDS:
            last_scan = now
            current = set(list_devices())
            seen &= current                       # forget devices that went away
            for path in sorted(current - seen):
                try:
                    dev = InputDevice(path)
                    keys = dev.capabilities().get(ecodes.EV_KEY, [])
                except OSError:
                    continue                      # try again next scan
                seen.add(path)
                if "razer" in dev.name.lower() and any(code in keys for code in hooks):
                    sel.register(dev, selectors.EVENT_READ)
                    print(f"Listening on {path} ({dev.name})", flush=True)
                else:
                    dev.close()

        if not sel.get_map():
            time.sleep(1.0)
            continue

        for key, _ in sel.select(timeout=1.0):
            dev = key.fileobj
            try:
                events = list(dev.read())
            except OSError:
                path = dev.path
                sel.unregister(dev)
                dev.close()
                print(f"Lost {path}", flush=True)
                continue
            for ev in events:
                if ev.type != ecodes.EV_KEY or ev.value != 1 or ev.code not in hooks:
                    continue
                t = time.monotonic()
                if t - last_fire.get(ev.code, -1e9) < DEBOUNCE_SECONDS:
                    continue
                last_fire[ev.code] = t
                threading.Thread(target=fire, args=(hooks[ev.code], args.dry_run), daemon=True).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
