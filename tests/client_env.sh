#!/bin/bash
# Runs a command as a client of the headless test shell in <scratch dir>.
# usage: client_env.sh <scratch dir> <command...>
scratch=$1; shift
exec env -u DISPLAY -u XAUTHORITY WAYLAND_DISPLAY=wayland-test XDG_RUNTIME_DIR="$scratch/runtime" \
  XDG_CONFIG_HOME="$scratch/config" XDG_DATA_HOME="$scratch/data" XDG_CACHE_HOME="$scratch/cache" \
  DBUS_SESSION_BUS_ADDRESS="$(cat "$scratch/bus")" GDK_BACKEND=wayland GSETTINGS_BACKEND=keyfile \
  XDG_SESSION_TYPE=wayland "$@"
