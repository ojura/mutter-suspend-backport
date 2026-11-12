#!/bin/bash
# Starts a separate headless gnome-shell for testing an extension, isolated
# from the desktop session: its own D-Bus session bus, runtime directory,
# settings (keyfile backend), data and cache directories.
#
# usage: headless_shell.sh <scratch dir> [extension source dir...]
# Writes <scratch>/bus (bus address) and <scratch>/shell.pid, logs to
# <scratch>/shell.log, and stays in the foreground until the shell exits.
set -euo pipefail

scratch=$1
shift
mkdir -p "$scratch"/{runtime,config,data,cache} "$scratch/data/gnome-shell/extensions"
chmod 700 "$scratch/runtime"

uuids=()
for extension in "$@"; do
  uuid=$(basename "$extension")
  cp -r "$extension" "$scratch/data/gnome-shell/extensions/$uuid"
  uuids+=("'$uuid'")
done
enabled="[$(IFS=,; echo "${uuids[*]:-}")]"
mkdir -p "$scratch/config/glib-2.0/settings"
cat > "$scratch/config/glib-2.0/settings/keyfile" <<SETTINGS
[org/gnome/shell]
enabled-extensions=$enabled
disable-user-extensions=false
welcome-dialog-last-shown-version='99.0'
SETTINGS

# TEST_CYCLE_OVERVIEW=1 makes the test helper extension open and close the
# Activities overview three times after the first window appears.
[ "${TEST_CYCLE_OVERVIEW:-0}" = 1 ] && touch "$scratch/runtime/test-cycle-overview"

exec env -u WAYLAND_DISPLAY -u DISPLAY -u GNOME_SHELL_SESSION_MODE -u DBUS_SESSION_BUS_ADDRESS \
  -u XAUTHORITY -u GNOME_SETUP_DISPLAY \
  XDG_RUNTIME_DIR="$scratch/runtime" XDG_CONFIG_HOME="$scratch/config" \
  XDG_DATA_HOME="$scratch/data" XDG_CACHE_HOME="$scratch/cache" \
  XDG_CURRENT_DESKTOP=GNOME XDG_SESSION_TYPE=wayland GSETTINGS_BACKEND=keyfile \
  dbus-run-session -- bash -c '
    echo "$DBUS_SESSION_BUS_ADDRESS" > "$1/bus"
    echo $$ > "$1/shell.pid"
    exec gnome-shell --headless --no-x11 --wayland-display=wayland-test \
      --virtual-monitor 1280x800 > "$1/shell.log" 2>&1
  ' bash "$scratch"
