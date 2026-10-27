# razer-idle-reactive

An idle color plus a reactive keypress effect for Razer keyboards on Linux.

Razer's built-in **Reactive** effect starts with every key dark and only lets you choose the
keypress color. This script runs the effect in software through
[OpenRazer](https://openrazer.github.io/) instead: all keys sit at an idle color (say, dim white
so you can see the keys), flash a second color (say, green) when pressed, and fade back.

One script, plus an optional JSON config file that lives outside the repo, so pulling updates
never overwrites your settings.

## Tested on

- Razer BlackWidow V4 X, Ubuntu, OpenRazer daemon 3.12.4

Other Razer keyboards supported by OpenRazer should work, but the **key positions in the LED
matrix differ by model**. See [Finding key positions](#finding-key-positions) to fix any that
light the wrong spot.

## Requirements

- OpenRazer daemon running and recognizing your keyboard
- Python 3 with `python3-openrazer` and `python3-evdev`
- Your user in the `input` group (the script reads key events from `/dev/input`; it does not
  grab or modify them)

```bash
sudo apt install python3-openrazer python3-evdev
sudo gpasswd -a $USER input      # then log out and back in
```

## Install

```bash
install -Dm755 razer-idle-reactive.py ~/.local/bin/razer-idle-reactive.py
install -Dm644 razer-idle-reactive.service ~/.config/systemd/user/razer-idle-reactive.service

# optional: your settings
mkdir -p ~/.config/razer-idle-reactive
cp config.example.json ~/.config/razer-idle-reactive/config.json

systemctl --user daemon-reload
systemctl --user enable --now razer-idle-reactive.service
```

Try it by hand first with `python3 ~/.local/bin/razer-idle-reactive.py` (Ctrl+C to stop).

Logs: `journalctl --user -u razer-idle-reactive`

## Configuration

Settings are read from `~/.config/razer-idle-reactive/config.json` (or `$XDG_CONFIG_HOME`, or
pass `--config PATH`). Every setting is optional; leave out anything you don't want to change.
Restart the service after editing: `systemctl --user restart razer-idle-reactive.service`.

| Setting | Default | Meaning |
|---|---|---|
| `base_color` | `[255, 255, 255]` | Idle color `[R, G, B]` |
| `base_level` | `0.25` | Idle intensity, 0.0 to 1.0 |
| `logged_out_base_level` | `null` | Idle intensity while nobody is logged in (see [below](#dark-at-the-login-screen)). `null` = same as `base_level` |
| `hit_color` | `[0, 255, 0]` | Keypress color `[R, G, B]` |
| `hit_level` | `1.0` | Keypress intensity, 0.0 to 1.0 |
| `fade` | `2.0` | Seconds for the keypress color to fade back to idle |
| `fps` | `30` | Redraw rate |
| `toggle_key` | `"KEY_F13"` | Key that pauses/resumes the effect (M1 on the V4 X). `null` disables it |
| `toggle_debounce` | `0.3` | Seconds to ignore duplicate toggle events |
| `keymap` | `{}` | Per-key LED position overrides (see below) |

A bad value stops the script with a message naming the setting; check the journal.

Tip: on many boards the red LEDs are weaker than green, so a dim equal mix can look tinted.
Nudge the channels if your idle color looks off.

## Pausing the effect (to use Polychromatic)

While the script runs it redraws the whole matrix every frame, so it will override anything
you apply in Polychromatic. Press the toggle key (M1 by default) to pause it: the keyboard
sits at the idle color and you can pick any other effect. Press it again to resume.

Note that the toggle key is also seen by your desktop, like any other key. F13 to F18 are
unused on most systems.

## Dark at the login screen

By default the effect stops when you log out, because both the OpenRazer daemon and this script
are *user* services. To keep it running at the login screen, with the keyboard dark until you
press a key, enable lingering and set a logged-out idle level:

```bash
sudo loginctl enable-linger $USER
```

```json
{
  "logged_out_base_level": 0.0
}
```

Lingering keeps your user's services running from boot and after logout. While nobody is logged
in, the idle level drops to `logged_out_base_level` (0.0 = dark) and keypresses still flash and
fade as usual. When you log in, the normal `base_level` returns. The lock screen counts as logged
in, so the idle color stays on while locked. Restart the service after changing the config.

## Finding key positions

The effect needs to know which LED belongs to which key. Defaults are in `build_keymap()` and
are verified only on the BlackWidow V4 X (6 rows x 22 columns).

Stop the service so it doesn't fight over the LEDs, then:

```bash
systemctl --user stop razer-idle-reactive.service
python3 ~/.local/bin/razer-idle-reactive.py --sweep 1       # light row 1 cell by cell, printing each position
python3 ~/.local/bin/razer-idle-reactive.py --probe 3 14    # light one cell and wait
```

Then correct any keys in the `keymap` section of your config:

```json
{
  "keymap": {
    "KEY_F5": [0, 7],
    "KEY_SPACE": [[5, 4], [5, 5]],
    "KEY_ESC": null
  }
}
```

- `[row, col]` sets a single cell, a list of them sets several (wide keys), and `null` removes
  the key from the effect.
- To see what name a physical key sends, use `evtest` or any evdev key monitor. On the V4 X the
  macro keys M1 to M6 send `KEY_F13` to `KEY_F18`, and their LEDs are in column 0 (M6 at the
  top down to M1 at the bottom).

## Troubleshooting

- **"No Razer keyboard input device found"**: you are probably not in the `input` group yet, or
  the keyboard's input name doesn't contain "razer".
- **"No Razer keyboard found via OpenRazer"**: check `systemctl --user status openrazer-daemon`.
- **A key lights the wrong spot**: see above.
- **A key never flashes**: check your `keymap` for a `null` entry for that key.
- **The effect disappears after you apply something in Polychromatic**: that's expected while
  the script is running; pause it with the toggle key first.

## License

MIT
