# ES-DE Attract Mode

A Big Box-style attract mode for [ES-DE](https://es-de.org/).

When the machine sits idle, it **drives the real ES-DE interface**: spinning the game
list like a roulette wheel, settling on a game long enough for the theme's video to
start, then backing out to the system carousel and diving into a different system.
Touch a control and it stops instantly.

> **This is not a plugin.** ES-DE has no addon system — only themes are extensible.
> This is a small companion daemon you run alongside it. It needs no changes to ES-DE
> itself and no patched build.

## Why not just use ES-DE's screensaver?

ES-DE ships a `video` screensaver, and it is good, but it is a different thing: it
takes over the screen with a fullscreen video on a blank canvas. Big Box's Attract Mode
never leaves the UI — you see your theme, your metadata panel, your artwork, and the
list visibly scrolling. That is what this reproduces.

## How it works

The interesting part is how input is delivered.

Synthetic **keystrokes** (xdotool and friends) only reach an application that holds
keyboard focus, so attract mode would stop the moment you clicked into another window.
Instead this creates a **virtual gamepad** via `/dev/uinput` and emits d-pad and button
events.

ES-DE is SDL-based, and SDL polls joysticks **regardless of window focus** when
`SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1` is set. So the attract loop keeps running
while you work in another window — which is the whole point, and something a keystroke
approach cannot do.

To know when to yield, the daemon reads raw events from `/dev/input`. Synthetic
uinput/XTEST events never appear on the *other* devices, so it can cleanly tell your
input from its own. Its own virtual device is excluded by path.

## Requirements

- ES-DE, launched with **`SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1`**
- Linux with `uinput` (any modern kernel)
- Python 3.8+ — **no third-party modules**
- Membership of the `input` group

Tested on CachyOS/Arch with KDE Plasma 6 on Wayland (ES-DE via XWayland). Nothing is
distro-specific; the systemd unit is the only packaging assumption.

## Install

```bash
git clone https://github.com/kyooknot/esde-attract-mode
cd esde-attract-mode
./install.sh
```

Then **log out and back in** if you were not already in the `input` group, and make sure
ES-DE is launched with the SDL variable above.

## Configuration

`~/.config/esde-attract.conf`, re-read every time attract mode starts — edit and wait,
no restart needed.

| key | default | what it does |
|---|---|---|
| `wait_time` | `180` | idle seconds before it starts |
| `dwell` | `12` | seconds parked on a game, so the theme's video has time to play |
| `spin_min` / `spin_max` | `22` / `55` | steps in a game-list spin |
| `speed_max` / `speed_min` | `0.008` / `0.45` | gap between steps: starts fast, ends slow |
| `ease` | `3.5` | deceleration curve. `1` is linear; higher holds the blur longer then settles sharply |
| `games_per_system` | `4` | games visited before changing system |
| `carousel_min` / `carousel_max` | `4` / `8` | steps when spinning the system carousel |
| `switch_systems` | `true` | set false to stay in one system |
| `watch` | `gamepad` | `gamepad` = only controllers interrupt, so it runs while you type elsewhere. `all` = any keyboard/mouse/controller (whole-machine idle) |

## Notes and gotchas

Things that cost real debugging time, recorded so they do not cost yours:

- **ES-DE's `Escape` is the MENU button, not Back.** Back is `BackSpace` (pad: **B**).
  Sending `Escape` on the system carousel opens the main menu, whose first entry is
  *Scraper* — a following "select" walks straight into your settings. This daemon never
  sends a menu key, and never sends **A** unless it knows it is on the carousel, because
  **A** in a gamelist *launches the game*.
- **Do not leave backup files in `~/.config/autostart/`.** systemd's
  `xdg-autostart-generator` does not filter on the `.desktop` extension, so
  `es-de.desktop.bak` will launch a second ES-DE.
- **`systemd --user` inherits your login group set** and will not see a later
  `usermod -aG input`. That is why the unit here is a *system* service with
  `SupplementaryGroups=input` — it needs no graphical session at all.
- **Wireless pads return on a new `/dev/input` node** after sleeping. The watcher
  rescans every 3 s; without that, nothing can interrupt attract mode after your
  controller wakes.
- **The virtual pad is destroyed while an emulator runs**, so it can never be
  enumerated as a controller port. udev orders pads by event number, so a pad that
  merely exists can take player 1 if your real controller reconnects on a higher number.
- The device is `0x1209:0xE5DE` ([pid.codes](https://pid.codes), the vendor ID for
  open-source projects) and is named honestly. Borrowing a real vendor's ID makes SDL
  substitute that vendor's product name; cloning a physical pad's identity makes it
  indistinguishable from the real device in ES-DE's controller list.

## Possible improvements

- ES-DE's help bar exposes **Random** and **System** actions. Driving those instead of
  counting d-pad steps would be tidier and immune to list length — their default
  bindings were not obvious from the binary.
- Nothing here is ES-DE-specific beyond the key choices. Any SDL frontend that enables
  background joystick events should work with a different button map.

## Licence

MIT
