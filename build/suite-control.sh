#!/bin/bash
# Runs the suspend tests of mutter's test suite, and the one test that
# failed in the package build, in a tree that dpkg-buildpackage has built.
# Runs inside the build container.
#
# usage: suite-control.sh <stock|stock-without-shield-case|patched> <package source dir>
#
# With "stock", the two window-actor patches from merge request 4588 are
# reversed first, so the tree is Ubuntu's 46.2 with only the test patches,
# and they are applied again at the end. Stock 46.2 does not suspend windows
# behind hidden window groups, so the upstream screen shield case waits until
# the test times out and the cases after it do not run;
# "stock-without-shield-case" also leaves out that one call in the test
# client, so that the hidden subsurface cases run on stock too. The tests run as the package
# build runs them (debian/rules), with the same timeout multiplier.
set -uo pipefail
mode=$1
cd "$2"
build=obj-x86_64-linux-gnu
fixes=(debian/patches/window-actor-Track-state-affecting-suspend-inhibation-ex.patch
       debian/patches/window-actor-Handle-visibility-condition-for-suspending-w.patch)

# dh_auto_test gives the tests a private runtime directory; mutter's
# Wayland tests refuse to start without one.
export XDG_RUNTIME_DIR=$(mktemp -d /tmp/xdg-runtime.XXXXXX)
chmod 700 "$XDG_RUNTIME_DIR"

run_tests() {
  for spec in "wayland-unit -p /wayland/toplevel/suspended" "suspend-state-timeout" "monitor-unit"; do
    set -- $spec
    name=$1; shift
    echo "=== $mode: meson test $name $*"
    env GIO_USE_VFS=local GIO_USE_VOLUME_MONITOR=unix GVFS_DISABLE_FUSE=1 \
      dbus-run-session -- xvfb-run -s '+iglx -noreset' -a \
      meson test -C "$build" --no-rebuild --verbose --timeout-multiplier 6 \
        --no-stdsplit --print-errorlogs ${*:+--test-args "$*"} "$name"
    echo "=== $mode: meson test $name exit status $?"
  done
}

client=src/tests/wayland-test-clients/xdg-toplevel-suspended.c
if [ "$mode" = stock ] || [ "$mode" = stock-without-shield-case ]; then
  patch -R -p1 < "${fixes[1]}" && patch -R -p1 < "${fixes[0]}" || exit 1
  if [ "$mode" = stock-without-shield-case ]; then
    cp "$client" "$client.orig-control"
    sed -i 's|^  test_screen_shield (display);$|  /* test_screen_shield (display); */|' "$client"
    grep -n 'test_screen_shield (display)' "$client"
  fi
  ninja -C "$build" || exit 1
  run_tests
  if [ "$mode" = stock-without-shield-case ]; then
    mv "$client.orig-control" "$client"
  fi
  patch -p1 < "${fixes[0]}" && patch -p1 < "${fixes[1]}" || exit 1
  ninja -C "$build" || exit 1
else
  run_tests
fi
