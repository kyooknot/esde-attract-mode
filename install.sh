#!/usr/bin/env bash
# Installs ES-DE attract mode. Run as your normal user; it will sudo where needed.
set -euo pipefail
U="${SUDO_USER:-$USER}"
H=$(getent passwd "$U" | cut -d: -f6)

echo "==> installing files to $H/.local/bin"
install -d "$H/.local/bin"
install -m 755 esde-attract   "$H/.local/bin/esde-attract"
install -m 644 esde_vpad.py   "$H/.local/bin/esde_vpad.py"
[ -f "$H/.config/esde-attract.conf" ] || install -m 644 esde-attract.conf.example "$H/.config/esde-attract.conf"

echo "==> granting access to /dev/uinput and /dev/input"
sudo install -m 644 99-uinput.rules /etc/udev/rules.d/99-uinput.rules
sudo modprobe uinput || true
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG input "$U"

echo "==> installing the service"
sed -e "s|REPLACE_HOME|$H|g" -e "s/REPLACE_ME/$U/g" esde-attract.service | sudo tee /etc/systemd/system/esde-attract.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now esde-attract

cat <<EOF

Done. Two things to check:

  1. ES-DE must run with SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1, or it will
     ignore the virtual pad unless it has focus. Add it to however you launch
     ES-DE, e.g. in ~/.config/autostart/es-de.desktop:
        Exec=env SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1 /path/to/ES-DE

  2. If you were not already in the 'input' group, log out and back in.

Watch it with:  journalctl -u esde-attract -f
Tune it in:     ~/.config/esde-attract.conf   (re-read each time it starts)
EOF
