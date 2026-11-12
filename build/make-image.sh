#!/bin/bash
# Builds the Docker image mutter-noble-build:46.2 with the
# build dependencies of mutter/debian/control.
# usage: build/make-image.sh
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
control=$here/../mutter/debian/control
context=$(mktemp -d /tmp/mutter-image-context.XXXXXX)
trap 'rm -rf "$context"' EXIT
cp "$here/Dockerfile" "$control" "$context/"
docker build --pull=false -t mutter-noble-build:46.2 "$context"
