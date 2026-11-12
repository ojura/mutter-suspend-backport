#!/bin/bash
# Builds the binary packages of one commit of this repository in the
# mutter-noble-build:46.2 container, through the AC guard, and then the
# source package on the host.
#
# usage: build/build-package.sh <commit> <jobs> <memory limit, e.g. 5g>
#
# The commit is checked out in a detached worktree under /tmp/mutter-build,
# because dpkg-buildpackage writes the packages to the parent directory of
# the package source. The container sees only that worktree, has no network,
# runs as the calling user, and is pinned to <jobs> CPUs with taskset, so
# that GCC's -flto=auto, meson test and ninja all use <jobs> processes.
# The packages, the build log and the guard's power and result records end
# up in out/<version>-<commit>/.
set -euo pipefail
commit=$(git rev-parse --short "$1")
jobs=$2
memory=$3
here=$(dirname "$(readlink -f "$0")")
repo=$(readlink -f "$here/..")
guard=$HOME/claude-skills/docker-ac-guard/scripts/docker_ac_guard.py
orig=$repo/out/ubuntu-source/mutter_46.2.orig.tar.xz

work=/tmp/mutter-build/$commit
[ -e "$work" ] && { echo "$work exists; remove it first" >&2; exit 1; }
mkdir -p /tmp/mutter-build
git -C "$repo" worktree add -q --detach "$work" "$commit"
version=$(dpkg-parsechangelog -l "$work/mutter/debian/changelog" -S Version)
out=$repo/out/$version-$commit
mkdir -p "$out"
ac_logs=$(mktemp -d "$out/ac-logs.XXXXXX")
chmod 700 "$ac_logs"

echo "building $version from $commit with $jobs jobs and $memory of memory"
status=0
DOCKER_AC_LOG_DIR=$ac_logs "$guard" run --rm --pull never --init \
  --name "mutter-build-$commit" --network none \
  --user "$(id -u):$(id -g)" --cpus "$jobs" --memory "$memory" \
  -v "$work:$work" -w "$work/mutter" \
  -e HOME=/tmp -e "DEB_BUILD_OPTIONS=parallel=$jobs" \
  mutter-noble-build:46.2 \
  taskset -c "0-$((jobs - 1))" dpkg-buildpackage -us -uc -b \
  > "$out/build.log" 2>&1 || status=$?
echo "container exit status $status"

if [ "$status" = 0 ]; then
  cp "$work"/*.deb "$work"/*.ddeb "$work"/*.buildinfo "$work"/*.changes "$out/"
  # The source package comes from a clean export of the commit, because the
  # built tree holds the build products.
  source=$(mktemp -d /tmp/mutter-source.XXXXXX)
  git -C "$repo" archive "$commit" mutter | tar -x -C "$source"
  cp "$orig" "$source/"
  (cd "$source" && dpkg-source -b mutter) >> "$out/build.log" 2>&1
  cp "$source"/*.dsc "$source"/*.debian.tar.xz "$out/"
  rm -rf "$source"
fi
echo "results in $out"
exit "$status"
