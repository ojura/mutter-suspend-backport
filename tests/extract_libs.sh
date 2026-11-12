#!/bin/bash
# Unpacks the libmutter-14-0 package of a build, so that run_cases.py can
# point the test shell at its libraries without installing anything.
# usage: tests/extract_libs.sh <build output dir> -> prints <dir>/root
set -euo pipefail
out=$(readlink -f "$1")
root=$out/root
deb=$(ls "$out"/libmutter-14-0_*.deb)
rm -rf "$root"
mkdir -p "$root"
dpkg-deb -x "$deb" "$root"
echo "$root"
