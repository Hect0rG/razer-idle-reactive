#!/usr/bin/env python3
"""
razer-idle-reactive - idle color + reactive keypress effect for Razer keyboards on Linux.

Razer's built-in "reactive" effect starts from black and only lets you choose the
keypress color. This script runs the effect in software through OpenRazer instead:
every key sits at an idle color, flashes a second color when pressed, then fades back.

Usage:
    razer-idle-reactive.py                   run the effect
    razer-idle-reactive.py --sweep [ROW]     light each matrix cell in turn (find key positions)
    razer-idle-reactive.py --probe ROW COL   light one cell and wait
    razer-idle-reactive.py --config PATH     use a specific config file

Settings live in a JSON file outside the program (default
~/.config/razer-idle-reactive/config.json), so updating the script never overwrites them.
Every setting is optional; anything you leave out uses the defaults below.
"""

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time

from evdev import InputDevice, ecodes, list_devices
from openrazer.client import DeviceManager

DEFAULTS = {
    "base_color": [255, 255, 255],   # idle color [R, G, B]
    "hit_color": [0, 255, 0],        # keypress color [R, G, B]
    "base_level": 0.25,              # idle intensity, 0.0 to 1.0
    "logged_out_base_level": None,   # idle intensity while nobody is logged in (needs lingering); null = same as base_level
    "hit_level": 1.0,                # keypress intensity, 0.0 to 1.0
    "fade": 2.0,                     # seconds for the keypress color to fade back to idle
    "fps": 30,                       # redraw rate
    "toggle_key": "KEY_F13",         # pauses/resumes the effect (M1 on a BlackWidow V4 X); null to disable
    "toggle_debounce": 0.3,          # seconds; one press can be reported on two input devices
}


# ------------------------------- config -------------------------------------
def default_config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "razer-idle-reactive", "config.json")


def validate(cfg, path):
    def bad(name, why):
        raise SystemExit(f"Config {path}: '{name}' {why}")

    for name in ("base_color", "hit_color"):
        v = cfg[name]
        if not (isinstance(v, (list, tuple)) and len(v) == 3
                and all(isinstance(x, int) and 0 <= x <= 255 for x in v)):
            bad(name, "must be [R, G, B] with whole numbers from 0 to 255")
    for name in ("base_level", "hit_level"):
        v = cfg[name]
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            bad(name, "must be a number from 0.0 to 1.0")
    lo = cfg["logged_out_base_level"]
    if lo is not None and (not isinstance(lo, (int, float)) or not 0 <= lo <= 1):
        bad("logged_out_base_level", "must be a number from 0.0 to 1.0, or null")
    if not isinstance(cfg["fade"], (int, float)) or cfg["fade"] <= 0:
        bad("fade", "must be a number greater than 0")
    if not isinstance(cfg["fps"], int) or cfg["fps"] <= 0:
        bad("fps", "must be a whole number greater than 0")
    if cfg["toggle_key"] is not None and not isinstance(cfg["toggle_key"], str):
        bad("toggle_key", 'must be a key name such as "KEY_F13", or null')
    if not isinstance(cfg["toggle_debounce"], (int, float)) or cfg["toggle_debounce"] < 0:
        bad("toggle_debounce", "must be a number of seconds, 0 or more")


def load_config(path, required):
    """Return (settings, keymap_overrides). A missing default config file is fine."""
    cfg = dict(DEFAULTS)
    if not os.path.exists(path):
        if required:
            raise SystemExit(f"Config file not found: {path}")
        return cfg, {}
    try:
        with open(path) as f:
            user = json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit(f"Could not read config {path}: {e}")
    if not isinstance(user, dict):
        raise SystemExit(f"Config {path} must be a JSON object")
    overrides = user.pop("keymap", {})
    if not isinstance(overrides, dict):
        raise SystemExit(f"Config {path}: 'keymap' must be an object")
    for key, val in user.items():
        if key in DEFAULTS:
            cfg[key] = val
        else:
            print(f"Warning: unknown setting {key!r} in {path} (ignored)", file=sys.stderr)
    validate(cfg, path)
    return cfg, overrides


# ------------------------------- key map ------------------------------------
def build_keymap(overrides):
    """evdev key name -> list of (row, col) matrix cells.

    Layout verified on a Razer BlackWidow V4 X (6 rows x 22 cols). Other models will
    likely differ; use --sweep to find positions and the "keymap" config section to fix them.
    """
    km = {}

    def add(row, start, names):
        for i, name in enumerate(names.split()):
            km[f"KEY_{name}"] = [(row, start + i)]

    add(0, 1, "ESC")
    add(0, 3, "F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12")
    add(0, 15, "SYSRQ SCROLLLOCK PAUSE")

    add(1, 1, "GRAVE 1 2 3 4 5 6 7 8 9 0 MINUS EQUAL BACKSPACE")
    add(1, 15, "INSERT HOME PAGEUP NUMLOCK KPSLASH KPASTERISK KPMINUS")

    add(2, 1, "TAB Q W E R T Y U I O P LEFTBRACE RIGHTBRACE BACKSLASH")
    add(2, 15, "DELETE END PAGEDOWN KP7 KP8 KP9")
    km["KEY_KPPLUS"] = [(2, 21), (3, 21)]

    add(3, 1, "CAPSLOCK A S D F G H J K L SEMICOLON APOSTROPHE")
    km["KEY_ENTER"] = [(3, 13), (3, 14)]
    add(3, 18, "KP4 KP5 KP6")

    km["KEY_LEFTSHIFT"] = [(4, 1), (4, 2)]
    add(4, 3, "Z X C V B N M COMMA DOT SLASH")
    km["KEY_RIGHTSHIFT"] = [(4, 13), (4, 14)]
    add(4, 16, "UP")
    add(4, 18, "KP1 KP2 KP3")
    km["KEY_KPENTER"] = [(4, 21)]

    add(5, 1, "LEFTCTRL LEFTMETA LEFTALT")
    km["KEY_SPACE"] = [(5, c) for c in range(4, 11)]
    add(5, 11, "RIGHTALT")
    add(5, 13, "COMPOSE RIGHTCTRL LEFT DOWN RIGHT")
    km["KEY_KP0"] = [(5, 18), (5, 19)]
    add(5, 20, "KPDOT")

    # Macro keys: M6 at the top of column 0 down to M1 at the bottom.
    # They arrive as KEY_F18 (M6) ... KEY_F13 (M1).
    for i, name in enumerate(["F18", "F17", "F16", "F15", "F14", "F13"]):
        km[f"KEY_{name}"] = [(i, 0)]

    # Overrides from the config file:
    #   "KEY_F5": [0, 7]                   one cell
    #   "KEY_SPACE": [[5, 4], [5, 5]]      several cells
    #   "KEY_ESC": null                    remove the key from the effect
    for name, val in overrides.items():
        if val is None:
            km.pop(name, None)
            continue
        try:
            if val and isinstance(val[0], int):
                cells = [tuple(val)]
            else:
                cells = [tuple(v) for v in val]
            if not all(len(c) == 2 and all(isinstance(x, int) for x in c) for c in cells):
                raise ValueError
        except (TypeError, ValueError):
            raise SystemExit(
                f"Bad keymap entry for {name}: expected [row, col], [[row, col], ...] or null"
            )
        km[name] = cells
    return km


# ------------------------------- helpers ------------------------------------
def scale(color, level):
    return tuple(int(c * level) for c in color)


def mix(base, hit, t):
    return tuple(int(b + (h - b) * t) for b, h in zip(base, hit))


def find_keyboard(dm):
    keyboards = [d for d in dm.devices if d.type == "keyboard"]
    if not keyboards:
        raise SystemExit("No Razer keyboard found via OpenRazer. Is openrazer-daemon running?")
    return keyboards[0]


def light_cell(fx, rows, cols, row, col, color=(255, 0, 0)):
    for r in range(rows):
        for c in range(cols):
            fx.matrix[r, c] = (0, 0, 0)
    fx.matrix[row, col] = color
    fx.draw()


def open_input_devices():
    sel = selectors.DefaultSelector()
    for path in list_devices():
        try:
            dev = InputDevice(path)
            keys = dev.capabilities().get(ecodes.EV_KEY, [])
        except OSError:
            continue
        if "razer" in dev.name.lower() and ecodes.KEY_A in keys:
            sel.register(dev, selectors.EVENT_READ)
    if not sel.get_map():
        raise SystemExit(
            "No Razer keyboard input device found. "
            "Are you in the 'input' group? (sudo gpasswd -a $USER input, then log out and in)"
        )
    return sel


# ------------------------------ login state ---------------------------------
SESSION_POLL_SECONDS = 2.0
LOGGED_OUT_STATES = {"lingering", "closing", "offline"}


def user_has_session():
    """True if this user has a login session. With lingering enabled, the user's services keep
    running after logout and systemd reports the state as 'lingering'."""
    try:
        out = subprocess.run(
            ["loginctl", "show-user", str(os.getuid()), "--property=State", "--value"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return True       # can't tell: behave as if logged in
    return out not in LOGGED_OUT_STATES


# ------------------------------- effect -------------------------------------
def run(kb, fx, rows, cols, cfg, overrides):
    base_in = scale(cfg["base_color"], cfg["base_level"])
    out_level = cfg["logged_out_base_level"]
    base_out = base_in if out_level is None else scale(cfg["base_color"], out_level)
    base = base_in           # idle color currently in use (changes with login state)
    logged_in = True
    last_poll = 0.0
    hit = scale(cfg["hit_color"], cfg["hit_level"])
    fade, fps, debounce = cfg["fade"], cfg["fps"], cfg["toggle_debounce"]

    code_to_cells = {}
    for name, cells in build_keymap(overrides).items():
        code = ecodes.ecodes.get(name)
        valid = [(r, c) for r, c in cells if 0 <= r < rows and 0 <= c < cols]
        if code is not None and valid:
            code_to_cells[code] = valid

    toggle_code = None
    if cfg["toggle_key"]:
        toggle_code = ecodes.ecodes.get(cfg["toggle_key"])
        if toggle_code is None:
            raise SystemExit(f"Unknown toggle_key: {cfg['toggle_key']!r}")

    sel = open_input_devices()
    heat = {}            # (row, col) -> time of last press
    enabled = True
    last_toggle = 0.0

    def draw(now):
        for r in range(rows):
            for c in range(cols):
                t0 = heat.get((r, c))
                t = max(0.0, 1.0 - (now - t0) / fade) if t0 else 0.0
                fx.matrix[r, c] = mix(base, hit, t)
        fx.draw()

    try:
        while True:
            poll_time = time.monotonic()
            if out_level is not None and poll_time - last_poll >= SESSION_POLL_SECONDS:
                last_poll = poll_time
                has_session = user_has_session()
                if has_session != logged_in:
                    logged_in = has_session
                    base = base_in if logged_in else base_out
                    print("Session state: " + ("logged in" if logged_in else "logged out"), flush=True)
                    if not enabled:
                        kb.fx.static(*base)
            for key, _ in sel.select(timeout=1.0 / fps):
                try:
                    events = list(key.fileobj.read())
                except OSError:
                    sel.unregister(key.fileobj)
                    if not sel.get_map():
                        raise SystemExit("Lost the keyboard input device")
                    continue
                for ev in events:
                    if ev.type != ecodes.EV_KEY or ev.value != 1:
                        continue
                    now = time.time()
                    if ev.code == toggle_code:
                        if now - last_toggle < debounce:
                            continue
                        last_toggle = now
                        enabled = not enabled
                        if enabled:
                            heat.clear()
                            for cell in code_to_cells.get(ev.code, []):
                                heat[cell] = now   # flash the toggle key itself
                        else:
                            # Hand the keyboard back: sit at the idle color so you can
                            # pick another effect in Polychromatic.
                            kb.fx.static(*base)
                    elif enabled and ev.code in code_to_cells:
                        for cell in code_to_cells[ev.code]:
                            heat[cell] = now
            if enabled:
                draw(time.time())
    except KeyboardInterrupt:
        pass
    finally:
        kb.fx.static(*base)


def main():
    ap = argparse.ArgumentParser(description="Idle color + reactive keypress effect for Razer keyboards.")
    ap.add_argument("--config", metavar="PATH",
                    help=f"config file (default: {default_config_path()})")
    ap.add_argument("--sweep", nargs="?", const="all", metavar="ROW",
                    help="light each matrix cell in turn (optionally just one row) and print its position")
    ap.add_argument("--probe", nargs=2, type=int, metavar=("ROW", "COL"),
                    help="light a single matrix cell and wait")
    args = ap.parse_args()

    cfg, overrides = load_config(args.config or default_config_path(), required=bool(args.config))

    # Turn `systemctl stop` into a clean exit so the keyboard is left in a known state.
    def _stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _stop)

    dm = DeviceManager()          # keep a reference alive for the whole run
    dm.sync_effects = False
    kb = find_keyboard(dm)
    fx = kb.fx.advanced
    rows, cols = fx.rows, fx.cols
    base = scale(cfg["base_color"], cfg["base_level"])

    if args.probe:
        row, col = args.probe
        if not (0 <= row < rows and 0 <= col < cols):
            raise SystemExit(f"Matrix is {rows} rows x {cols} cols (0-based).")
        light_cell(fx, rows, cols, row, col)
        try:
            input(f"Lit row {row}, col {col}. Press Enter to exit...")
        finally:
            kb.fx.static(*base)
        return

    if args.sweep:
        sweep_rows = range(rows) if args.sweep == "all" else [int(args.sweep)]
        print(f"Matrix is {rows} rows x {cols} cols. Watch the keyboard; Ctrl+C to stop.")
        try:
            for r in sweep_rows:
                for c in range(cols):
                    print(f"row {r}, col {c}")
                    light_cell(fx, rows, cols, r, c)
                    time.sleep(0.7)
        except KeyboardInterrupt:
            pass
        finally:
            kb.fx.static(*base)
        return

    run(kb, fx, rows, cols, cfg, overrides)


if __name__ == "__main__":
    sys.exit(main())
