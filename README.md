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

- A Razer keyboard supported by OpenRazer (tested: BlackWidow V4 X)
- The OpenRazer daemon, running and recognizing your keyboard
- Python 3 with `python3-openrazer` and `python3-evdev`
- Your user in the `input` group (the script reads key events from `/dev/input`; it does not
  grab or modify them)
- `git`, or a way to download and unzip the project

## Install

These steps are for Ubuntu and other Debian-based systems. Run them in order.

### 1. Install the prerequisites

```bash
sudo apt install python3-openrazer python3-evdev
sudo gpasswd -a $USER input
```

On a fresh system this pulls in about 45 packages (roughly 250 MB), including compilers and the
OpenRazer kernel driver, which is built with DKMS during the install. It can take a few minutes.
If Secure Boot is enabled, Ubuntu may ask you to set a password and enroll a key on the next boot
so the driver can load.

### 2. Reboot

The driver needs to load, the `input` group change needs a fresh login, and the OpenRazer daemon
starts at login. Rebooting covers all three. (At the least, log out and back in, and unplug and
re-plug the keyboard.)

### 3. Check that OpenRazer sees your keyboard

```bash
lsmod | grep razer                       # the razerkbd driver should be listed
groups | grep input                      # you should be in the input group
systemctl --user status openrazer-daemon --no-pager
python3 -c "from openrazer.client import DeviceManager; print([(d.name, d.type) for d in DeviceManager().devices])"
```

The last command should print your keyboard, for example
`[('Razer BlackWidow V4 X', 'keyboard')]`. If the list is empty, OpenRazer doesn't recognize your
keyboard yet; see [Troubleshooting](#troubleshooting) before going further.

### 4. Get the project

```bash
sudo apt install git        # if you don't have it
git clone https://github.com/Hect0rG/razer-idle-reactive.git
cd razer-idle-reactive
```

No git? Use **Code > Download ZIP** on GitHub, unzip it, and `cd` into the folder. The commands in
the next step only work from inside the project folder.

### 5. Install the script and service

```bash
install -Dm755 razer-idle-reactive.py ~/.local/bin/razer-idle-reactive.py
install -Dm644 razer-idle-reactive.service ~/.config/systemd/user/razer-idle-reactive.service

# optional: create your config file (see "Editing the config file" below)
mkdir -p ~/.config/razer-idle-reactive
cp config.example.json ~/.config/razer-idle-reactive/config.json

systemctl --user daemon-reload
systemctl --user enable --now razer-idle-reactive.service
```

### 6. Check that it's running

```bash
systemctl --user status razer-idle-reactive.service --no-pager
journalctl --user -u razer-idle-reactive
```

The status should say `active (running)`, and your keys should sit at the idle color and flash on
press. To try it by hand instead, run `python3 ~/.local/bin/razer-idle-reactive.py` (Ctrl+C to
stop).

## Configuration

Settings are read from `~/.config/razer-idle-reactive/config.json` (or `$XDG_CONFIG_HOME`, or
pass `--config PATH`). Every setting is optional; leave out anything you don't want to change.
Restart the service after editing: `systemctl --user restart razer-idle-reactive.service`.
New to this? See [Editing the config file](#editing-the-config-file) below.

| Setting | Default | Meaning |
|---|---|---|
| `base_color` | `[255, 255, 255]` | Idle color `[R, G, B]` |
| `base_level` | `0.25` | Idle intensity, 0.0 to 1.0 |
| `logged_out_base_level` | `null` | Idle intensity while nobody is logged in (see [below](#dark-at-the-login-screen)). `null` = same as `base_level` |
| `locked_base_level` | `null` | Idle intensity while the screen is locked. `null` = same as `base_level` |
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

### Editing the config file

The config file is `~/.config/razer-idle-reactive/config.json` (`~` is your home folder). It lives
outside the project folder on purpose, so updating the project never overwrites your settings.

**If the file doesn't exist yet**, create it from the example. Run this from inside the project
folder:

```bash
mkdir -p ~/.config/razer-idle-reactive
cp config.example.json ~/.config/razer-idle-reactive/config.json
```

**Edit it** with any text editor, for example:

```bash
nano ~/.config/razer-idle-reactive/config.json
```

(In nano, save with Ctrl+O then Enter, and exit with Ctrl+X.) All settings go inside one pair of
curly braces, as `"name": value` lines, and every line except the last needs a comma at the end. A
complete example:

```json
{
  "base_level": 0.25,
  "logged_out_base_level": 0.0,
  "locked_base_level": 0.0,
  "fade": 2.0
}
```

When another section of this README shows a snippet like `"logged_out_base_level": 0.0`, add that
line inside the braces of this file, next to your other settings. Don't paste a second `{ }` block,
and mind the commas.

**Check and apply your changes:**

```bash
python3 -m json.tool ~/.config/razer-idle-reactive/config.json > /dev/null && echo "config OK" && systemctl --user restart razer-idle-reactive.service
```

The restart only happens if the file is valid JSON. If it isn't, the error names a line. For
example, `Expecting ',' delimiter: line 3` usually means the line above it is missing its comma.

## Pausing the effect (to use Polychromatic)

While the script runs it redraws the whole matrix every frame, so it will override anything
you apply in Polychromatic. Press the toggle key (M1 by default) to pause it: the keyboard
sits at the idle color and you can pick any other effect. Press it again to resume.
Polychromatic is optional; [here's how to install it](#optional-polychromatic-a-gui).

Note that the toggle key is also seen by your desktop, like any other key, and on many desktops F13
(M1) opens the Settings app. See [below](#m1-opens-settings-or-another-desktop-action) to change that.

### M1 opens Settings (or another desktop action)

This script only listens to key presses and doesn't block them, so your desktop sees every press
too. Linux's standard keyboard layout turns the macro keys into media-style keys: F13 (M1) becomes
`XF86Tools`, which GNOME and KDE bind to their Settings app by default, and F14 to F18 (M2 to M6)
become `XF86Launch5` to `XF86Launch9`, which are normally unbound.

To see what your desktop has bound to those keys (GNOME):

```bash
gsettings list-recursively | grep -E "XF86Tools|XF86Launch"
```

On GNOME the Settings shortcut is stored as `control-center-static`. To free M1 so it only toggles
the effect:

```bash
gsettings set org.gnome.settings-daemon.plugins.media-keys control-center-static "[]"
```

To open Settings from M2 instead, also set the editable Settings shortcut:

```bash
gsettings set org.gnome.settings-daemon.plugins.media-keys control-center-static "[]"
gsettings set org.gnome.settings-daemon.plugins.media-keys control-center "['XF86Launch5']"
```

If a change doesn't take effect right away, log out and back in. To undo it:

```bash
gsettings reset org.gnome.settings-daemon.plugins.media-keys control-center-static
gsettings reset org.gnome.settings-daemon.plugins.media-keys control-center
```

Don't use M2 for both Settings and a webhook, because one press would do both. Another option is to
leave the desktop alone and move the toggle to another macro key with `"toggle_key": "KEY_F14"` in
your [config file](#editing-the-config-file). On other desktops, look for `XF86Tools` in the keyboard shortcut settings.

## Optional: Polychromatic (a GUI)

razer-idle-reactive is a background script with no window. If you also want a graphical app for
Razer's built-in effects, per-key colors, brightness and your other Razer devices, install
[Polychromatic](https://polychromatic.app/), which works on top of OpenRazer. Use it while this
effect is paused (press the toggle key, M1 by default), because the script redraws the keyboard every
frame and would otherwise override what you pick.

First see whether your distro already packages it:

```bash
apt policy polychromatic
```

If it shows a candidate version, install it with `sudo apt install polychromatic`. Otherwise, or if
you want the newest versions of OpenRazer and Polychromatic, use the projects' PPAs:

```bash
sudo add-apt-repository ppa:openrazer/stable
sudo add-apt-repository ppa:polychromatic/stable
sudo apt update
sudo apt install openrazer-meta polychromatic
```

- If you already installed OpenRazer in the install steps above, the PPA upgrades it. Reboot afterwards,
  because the kernel driver is rebuilt.
- PPAs can lag behind new Ubuntu releases. If `apt update` says a PPA "does not have a Release file",
  remove it with `sudo add-apt-repository --remove ppa:openrazer/stable` (or
  `ppa:polychromatic/stable`) and use your distro's packages instead.
- Open Polychromatic from your application menu. Pause this effect first (see
  [Pausing the effect](#pausing-the-effect-to-use-polychromatic)).
- Other distros: see the install pages at [openrazer.github.io](https://openrazer.github.io/) and
  [polychromatic.app](https://polychromatic.app/).

## Dark at the login screen

By default the effect stops when you log out, because both the OpenRazer daemon and this script are
*user* services. To keep it running at the login screen, with the keyboard dark until you press a
key:

**1. Enable lingering**, which keeps your user's services running from boot and after logout:

```bash
sudo loginctl enable-linger $USER
```

**2. Add the setting to your config file**, `~/.config/razer-idle-reactive/config.json` (see
[Editing the config file](#editing-the-config-file) if it doesn't exist yet). Put this line inside
the braces, next to your other settings, and mind the commas:

```json
"logged_out_base_level": 0.0
```

For example, the whole file might look like this:

```json
{
  "base_level": 0.25,
  "logged_out_base_level": 0.0
}
```

**3. Check the file and restart the service:**

```bash
python3 -m json.tool ~/.config/razer-idle-reactive/config.json > /dev/null && echo "config OK" && systemctl --user restart razer-idle-reactive.service
```

**4. Try it.** Log out: the keyboard should be dark at the login screen, and each key press should
flash and fade. After you log back in, you can confirm the switch happened:

```bash
journalctl --user -u razer-idle-reactive | grep "Session state"
```

You should see `Session state: logged out` and then `Session state: logged in`.

While nobody is logged in, the idle level drops to `logged_out_base_level` (0.0 = dark) and
keypresses still flash and fade as usual. When you log in, the normal `base_level` returns.

**Dark while the screen is locked too:** add `"locked_base_level": 0.0` to the same file (as in the
example in [Editing the config file](#editing-the-config-file)). Keypresses still flash. The locked
state comes from logind's `LockedHint`, which GNOME sets; other desktops may not.

OpenRazer can also switch the keyboard off by itself when the screensaver starts, which hides
keypress effects while locked. If you want the effect to show then, set
`devices_off_on_screensaver = False` under `[Startup]` in `~/.config/openrazer/razer.conf`, then
restart the daemon (`systemctl --user restart openrazer-daemon.service`).

## Finding key positions

The effect needs to know which LED belongs to which key. Defaults are in `build_keymap()` and
are verified only on the BlackWidow V4 X (6 rows x 22 columns).

Stop the service so it doesn't fight over the LEDs, then:

```bash
systemctl --user stop razer-idle-reactive.service
python3 ~/.local/bin/razer-idle-reactive.py --sweep 1       # light row 1 cell by cell, printing each position
python3 ~/.local/bin/razer-idle-reactive.py --probe 3 14    # light one cell and wait
```

Then correct any keys in the `keymap` section of your config file
(`~/.config/razer-idle-reactive/config.json`; see [Editing the config file](#editing-the-config-file)).
The `keymap` entry goes inside the same braces as your other settings, so add it next to them
instead of pasting a second `{ }` block:

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

## Optional: macro keys that trigger webhooks

The macro keys (M1 to M6 on a BlackWidow V4 X) can trigger anything that accepts a web request,
such as a Home Assistant webhook. A small system service in [`extras/macro-webhooks/`](extras/macro-webhooks)
does this. Because it runs from boot instead of inside your login session, it keeps working at the
login screen, where desktop keyboard shortcuts don't exist.

It is separate from the lighting script. It only reads key presses and sends HTTP requests, and it
never touches the LEDs.

### How the keys map

| Key | Key name | Desktop sees it as | LED cell (row, col) |
|---|---|---|---|
| M1 | `KEY_F13` | `XF86Tools` (opens Settings) | 5, 0 |
| M2 | `KEY_F14` | `XF86Launch5` | 4, 0 |
| M3 | `KEY_F15` | `XF86Launch6` | 3, 0 |
| M4 | `KEY_F16` | `XF86Launch7` | 2, 0 |
| M5 | `KEY_F17` | `XF86Launch8` | 1, 0 |
| M6 | `KEY_F18` | `XF86Launch9` | 0, 0 |

M1, M5 and M6 were checked on a BlackWidow V4 X; M2 to M4 follow the same pattern. On other models,
find the names with the key finder below and the LED cells with `--sweep` (see
[Finding key positions](#finding-key-positions)).

M1 is this project's pause/resume key by default (`toggle_key`), so use M2 to M6 for webhooks, or
change `toggle_key` in your
[config file](#editing-the-config-file).

To see which name a key sends, run this and press it (Ctrl+C to quit):

```bash
sudo python3 - <<'EOF'
from evdev import InputDevice, list_devices, ecodes
import selectors
sel = selectors.DefaultSelector()
for p in list_devices():
    d = InputDevice(p)
    if "razer" in d.name.lower():
        sel.register(d, selectors.EVENT_READ)
print("Press a key (Ctrl+C to quit)")
while True:
    for k, _ in sel.select():
        for ev in k.fileobj.read():
            if ev.type == ecodes.EV_KEY and ev.value == 1:
                print(ecodes.KEY.get(ev.code) or ev.code)
EOF
```

One press can print twice, because the keyboard exposes more than one input device. The service
ignores the duplicate.

### Set it up

From the project folder:

```bash
cd extras/macro-webhooks

# your webhook URLs go in a root-only file outside the project
sudo install -m 600 webhooks.example.json /etc/razer-macro-webhooks.json
sudo nano /etc/razer-macro-webhooks.json
sudo python3 -m json.tool /etc/razer-macro-webhooks.json > /dev/null && echo "JSON OK"

# install and start the service
sudo install -m 755 razer-macro-webhooks.py /usr/local/bin/razer-macro-webhooks.py
sudo install -m 644 razer-macro-webhooks.service /etc/systemd/system/razer-macro-webhooks.service
sudo systemctl daemon-reload
sudo systemctl enable --now razer-macro-webhooks.service
sudo systemctl status razer-macro-webhooks.service --no-pager
```

The config maps key names to URLs. Each value must be only the URL, not a `curl` command:

```json
{
  "KEY_F18": "http://homeassistant.local:8123/api/webhook/YOUR_ID",
  "KEY_F17": {"url": "http://homeassistant.local:8123/api/webhook/OTHER_ID", "method": "POST"}
}
```

- The default method is `POST`. `PUT` and `GET` are also accepted, using the object form above.
- Webhook IDs work like passwords. Keep them in `/etc/razer-macro-webhooks.json` (root-only), never in
  the project folder or in git.
- Restart after editing: `sudo systemctl restart razer-macro-webhooks.service`.

To try it without sending anything, run the service in dry-run mode, which prints each key press it
sees:

```bash
sudo python3 razer-macro-webhooks.py --dry-run --config webhooks.example.json
```

Watch real requests with `sudo journalctl -u razer-macro-webhooks -f`. A working press logs a line
like `KEY_F18: POST -> HTTP 200`. The log never prints your URLs.

### Things to know

- **Remove any desktop shortcut bound to the same key.** Otherwise a press fires twice (once from the
  shortcut, once from the service), and a toggle webhook will flip on and straight back off.
- **Keep the OpenRazer daemon running after you log out.** In testing, the macro keys sent nothing
  when the daemon was stopped. Enable lingering so the daemon keeps running at the login screen:
  `sudo loginctl enable-linger $USER` (see [Dark at the login screen](#dark-at-the-login-screen)).
- **The service only listens; it doesn't block the keys.** Your desktop still sees F13 to F18, and
  M1 (F13) opens the Settings app by default. See
  [M1 opens Settings](#m1-opens-settings-or-another-desktop-action) to free it or move it.
- **`needs an http:// or https:// url` in the log** means a value in the config isn't a bare URL. A
  pasted `curl ...` command or a stray space or quote is the usual cause.

## Troubleshooting

- **M1 opens the Settings app**: that's the desktop's default for F13. See
  [M1 opens Settings](#m1-opens-settings-or-another-desktop-action).
- **`install: cannot stat 'razer-idle-reactive.py'` (or the same error from `cp`)**: you're not
  inside the project folder. `cd` into the cloned or unzipped folder and run `ls`; you should see
  `razer-idle-reactive.py`, `razer-idle-reactive.service` and `config.example.json`.
- **The device list in install step 3 is empty**: reboot if you haven't since installing the
  prerequisites, then check `lsmod | grep razer`. If the driver is loaded and the list is still
  empty, the OpenRazer version in your distro may be too old for your keyboard model. Check the
  supported device list at [openrazer.github.io](https://openrazer.github.io/) and install a newer
  OpenRazer release from the OpenRazer PPA (see [Optional: Polychromatic](#optional-polychromatic-a-gui)).
  Some setups also need your user in the `plugdev` group: `sudo gpasswd -a $USER plugdev`, then reboot.
- **Permission errors reading `/dev/input`**: you're not in the `input` group in your current
  login session yet. Log out and back in (or reboot) after `sudo gpasswd -a $USER input`.
- **The service stops right after starting**: read the last lines of
  `journalctl --user -u razer-idle-reactive -n 30`. A mistake in your config file is reported there
  with the name of the setting.
- **"No Razer keyboard input device found"**: you are probably not in the `input` group yet, or
  the keyboard's input name doesn't contain "razer".
- **"No Razer keyboard found via OpenRazer"**: check `systemctl --user status openrazer-daemon`.
- **A key lights the wrong spot**: see above.
- **A key never flashes**: check your `keymap` for a `null` entry for that key.
- **The effect disappears after you apply something in Polychromatic**: that's expected while
  the script is running; pause it with the toggle key first.

## License

MIT
